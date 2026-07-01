import os
import sys
import hashlib
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
        
    network = os.getenv('DOCKER_NETWORK', 'bridge')
    
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
        provider = config.get('llmProvider', 'openai')
        api_key = config.get('llmApiKey', '')
        
        environment = {
            "TELEGRAM_BOT_TOKEN": token,
            "SUPABASE_URL": config.get('supabaseUrl', ''),
            "SUPABASE_SERVICE_ROLE_KEY": config.get('supabaseKey', ''),
            "LLM_PROVIDER": provider,
            "LLM_MODEL": config.get('llmModel', 'gpt-4o-mini'),
            "EMBEDDING_MODEL": config.get('embeddingModel', 'text-embedding-3-small'),
            
            "OPENAI_API_KEY": api_key if provider == 'openai' else '',
            "GOOGLE_API_KEY": api_key if provider == 'gemini' else '',
            "GROQ_API_KEY": api_key if provider == 'groq' else '',
            "OPENROUTER_API_KEY": api_key if provider == 'openrouter' else '',
            
            "CHUNK_SIZE": str(config.get('chunkSize', 1000)),
            "CHUNK_OVERLAP": str(config.get('chunkOverlap', 200)),
            "RETRIEVER_K": str(config.get('retrieverK', 10))
        }
    else:
        # GitHub PR Bot
        image_name = "github_pr_bot"
        environment = {
            "TELEGRAM_BOT_TOKEN": token,
            "GEMINI_API_KEY": config.get('geminiApiKey', ''),
            "GITHUB_TOKEN": config.get('githubToken', ''),
            "MAX_REPO_SIZE_MB": str(config.get('maxRepoSize', 100)),
            "GITHUB_CLIENT_ID": config.get('githubClientId', ''),
            "GITHUB_CLIENT_SECRET": config.get('githubClientSecret', ''),
            "OAUTH_REDIRECT_URL": config.get('oauthRedirectUrl', ''),
            "PORT": "3000"
        }

    container = get_client().containers.run(
        image=image_name,
        name=container_name,
        environment=environment,
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        network=network
    )
    
    return {
        "success": True, 
        "message": f"{bot_type.upper()} container started successfully", 
        "container_id": container.id
    }

def stop_bot_container(token: str) -> dict:
    hash_id = get_bot_hash(token)
    for prefix in ["anjani-bot", "pdf-bot", "gh-pr-bot"]:
        container_name = f"{prefix}-{hash_id}"
        try:
            container = get_client().containers.get(container_name)
            container.stop()
            container.remove(force=True)
            return {"success": True, "message": "Bot container stopped and removed"}
        except docker.errors.NotFound:
            pass
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
