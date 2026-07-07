import os
import sys
import hashlib
from pathlib import Path
import docker

_client = None

def get_client():
    global _client
    if _client is not None:
        return _client
        
    try:
        _client = docker.from_env()
        return _client
    except Exception:
        pass
        
    try:
        if sys.platform == 'win32':
            _client = docker.DockerClient(base_url='npipe:////./pipe/docker_engine')
        else:
            _client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        return _client
    except Exception as e:
        raise docker.errors.DockerException(
            f"Failed to connect to Docker daemon. Make sure Docker is running. Error: {e}"
        )

def get_bot_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]

def launch_bot_container(token: str, bot_type: str, config: dict) -> dict:
    hash_id = get_bot_hash(token)
    
    if bot_type == "anjani":
        prefix = "anjani-bot"
    elif bot_type == "ai_pdf_chat":
        prefix = "pdf-bot"
    else:
        prefix = "gh-pr-bot"
        
    container_name = f"{prefix}-{hash_id}"
    
    # Try stopping any existing container for this token under all three prefixes
    for pref in ["anjani-bot", "pdf-bot", "gh-pr-bot"]:
      try:
        existing = get_client().containers.get(f"{pref}-{hash_id}")
        existing.remove(force=True)
      except docker.errors.NotFound:
        pass
        
    # Anjani needs the custom network to reach the MongoDB container.
    # AI PDF and GitHub PR bots only need internet access (Telegram API,
    # Supabase, GitHub), so they use the default bridge network which has
    # reliable DNS resolution via the Docker daemon.
    custom_network = os.getenv('DOCKER_NETWORK', 'bridge')
    if bot_type == "anjani":
        network = custom_network
    else:
        network = "bridge"

    volumes = None  # Volume mounts (used by ai_pdf_chat for .env file)
    
    if bot_type == "anjani":
        image_name = "anjani"
        api_id = os.getenv('API_ID', '')
        api_hash = os.getenv('API_HASH', '')
        base_db_uri = os.getenv('DB_URI_TEMPLATE', 'mongodb://localhost:27017')
        bot_db_uri = base_db_uri.replace('{HASH}', hash_id) if '{HASH}' in base_db_uri else f"{base_db_uri}/anjani_bot_{hash_id}"
        
        environment = {
            "API_ID": api_id,
            "API_HASH": api_hash,
            "BOT_TOKEN": token,
            "OWNER_ID": config.get('ownerId', ''),
            "DB_URI": bot_db_uri,
            "ENABLED_PLUGINS": ";".join(config.get('enabledPlugins', []))
        }
    elif bot_type == "ai_pdf_chat":
        image_name = "ai_chatbot_pdf"
        environment = {
            "TELEGRAM_BOT_TOKEN": token,
        }
        
        # Only add keys if they are truthy to prevent overwriting values from mounted .env
        if config.get('supabaseUrl'):
            environment["SUPABASE_URL"] = config['supabaseUrl']
        if config.get('supabaseKey'):
            environment["SUPABASE_SERVICE_ROLE_KEY"] = config['supabaseKey']
        if config.get('llmProvider'):
            environment["LLM_PROVIDER"] = config['llmProvider']
        if config.get('llmModel'):
            environment["LLM_MODEL"] = config['llmModel']
        if config.get('embeddingModel'):
            environment["EMBEDDING_MODEL"] = config['embeddingModel']
            
        provider = config.get('llmProvider', 'openai')
        api_key = config.get('llmApiKey', '')
        if api_key:
            if provider == 'openai':
                environment["OPENAI_API_KEY"] = api_key
            elif provider == 'gemini':
                environment["GOOGLE_API_KEY"] = api_key
            elif provider == 'groq':
                environment["GROQ_API_KEY"] = api_key
            elif provider == 'openrouter':
                environment["OPENROUTER_API_KEY"] = api_key
            elif provider == 'g0i':
                environment["G0I_API_KEY"] = api_key
            elif provider == 'nvidia':
                environment["NVIDIA_API_KEY"] = api_key
                
        if config.get('chunkSize'):
            environment["CHUNK_SIZE"] = str(config['chunkSize'])
        if config.get('chunkOverlap'):
            environment["CHUNK_OVERLAP"] = str(config['chunkOverlap'])
        if config.get('retrieverK'):
            environment["RETRIEVER_K"] = str(config['retrieverK'])
        
        # Mount the bot's .env file into the container so that multi-key configs
        # (GOOGLE_API_KEYS for embedding rotation, G0I_API_KEY, etc.) are available.
        # The bot's config.py loads from /app/.env via python-dotenv.
        # Docker env vars (above) take precedence over .env since dotenv won't override.
        env_file = Path(__file__).resolve().parent.parent.parent.parent / "bots" / "ai_chatbot_pdf" / ".env"
        if env_file.exists():
            volumes = {str(env_file): {"bind": "/app/.env", "mode": "ro"}}
    else:
        # GitHub PR Bot
        image_name = "github_pr_bot"
        environment = {
            "TELEGRAM_BOT_TOKEN": token,
            "PORT": "3000"
        }
        if config.get('geminiApiKey'):
            environment["GEMINI_API_KEY"] = config['geminiApiKey']
        if config.get('githubToken'):
            environment["GITHUB_TOKEN"] = config['githubToken']
        if config.get('maxRepoSize'):
            environment["MAX_REPO_SIZE_MB"] = str(config['maxRepoSize'])
        if config.get('githubClientId'):
            environment["GITHUB_CLIENT_ID"] = config['githubClientId']
        if config.get('githubClientSecret'):
            environment["GITHUB_CLIENT_SECRET"] = config['githubClientSecret']
        if config.get('oauthRedirectUrl'):
            environment["OAUTH_REDIRECT_URL"] = config['oauthRedirectUrl']

        env_file = Path(__file__).resolve().parent.parent.parent.parent / "bots" / "github_pr_bot" / ".env"
        if env_file.exists():
            volumes = {str(env_file): {"bind": "/app/.env", "mode": "ro"}}

    run_kwargs = {
        "image": image_name,
        "name": container_name,
        "environment": environment,
        "detach": True,
        "restart_policy": {"Name": "unless-stopped"},
        "network": network,
        # Explicit public DNS servers prevent "Name or service not known" errors
        # when the Docker network's embedded DNS has temporary failures.
        "dns": ["8.8.8.8", "8.8.4.4"],
    }
    if volumes:
        run_kwargs["volumes"] = volumes
    
    container = get_client().containers.run(**run_kwargs)
    
    return {
        "success": True, 
        "message": f"{bot_type.upper()} container started successfully", 
        "container_id": container.id
    }

def stop_bot_container(token: str) -> dict:
    hash_id = get_bot_hash(token)
    stopped_any = False
    for prefix in ["anjani-bot", "pdf-bot", "gh-pr-bot"]:
        container_name = f"{prefix}-{hash_id}"
        try:
            container = get_client().containers.get(container_name)
            container.stop()
            container.remove(force=True)
            stopped_any = True
        except docker.errors.NotFound:
            pass
    if stopped_any:
        return {"success": True, "message": "Bot containers stopped and removed"}
    return {"success": True, "message": "Bot was already stopped"}

def get_bot_container_status(token: str) -> dict:
    hash_id = get_bot_hash(token)
    for prefix in ["anjani-bot", "pdf-bot", "gh-pr-bot"]:
        container_name = f"{prefix}-{hash_id}"
        try:
            container = get_client().containers.get(container_name)
            return {
                "status": "running" if container.status == "running" else "stopped",
                "container_id": container.id,
                "started_at": container.attrs.get('State', {}).get('StartedAt')
            }
        except docker.errors.NotFound:
            pass
    return {"status": "stopped", "container_id": None, "started_at": None}
