import os
import sys
import hashlib
import docker

try:
    client = docker.from_env()
except Exception:
    if sys.platform == 'win32':
        client = docker.DockerClient(base_url='npipe:////./pipe/docker_engine')
    else:
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')

def get_bot_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]

def launch_bot_container(token: str, bot_type: str, config: dict) -> dict:
    hash_id = get_bot_hash(token)
    prefix = "anjani-bot" if bot_type == "anjani" else "pdf-bot"
    container_name = f"{prefix}-{hash_id}"
    
    # Try stopping any existing container for this token under either prefix
    for pref in ["anjani-bot", "pdf-bot"]:
        try:
            existing = client.containers.get(f"{pref}-{hash_id}")
            if existing.status == 'running' and pref == prefix:
                return {
                    "success": True, 
                    "message": "Bot is already running", 
                    "container_id": existing.id
                }
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
    else:
        # AI PDF Chatbot (RAG)
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
            
            # Conditionally map key based on provider
            "OPENAI_API_KEY": api_key if provider == 'openai' else '',
            "GOOGLE_API_KEY": api_key if provider == 'gemini' else '',
            "GROQ_API_KEY": api_key if provider == 'groq' else '',
            "OPENROUTER_API_KEY": api_key if provider == 'openrouter' else '',
            
            "CHUNK_SIZE": str(config.get('chunkSize', 1000)),
            "CHUNK_OVERLAP": str(config.get('chunkOverlap', 200)),
            "RETRIEVER_K": str(config.get('retrieverK', 10))
        }

    container = client.containers.run(
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
    for prefix in ["anjani-bot", "pdf-bot"]:
        container_name = f"{prefix}-{hash_id}"
        try:
            container = client.containers.get(container_name)
            container.stop()
            container.remove(force=True)
            return {"success": True, "message": "Bot container stopped and removed"}
        except docker.errors.NotFound:
            pass
    return {"success": True, "message": "Bot was already stopped"}

def get_bot_container_status(token: str) -> dict:
    hash_id = get_bot_hash(token)
    for prefix in ["anjani-bot", "pdf-bot"]:
        container_name = f"{prefix}-{hash_id}"
        try:
            container = client.containers.get(container_name)
            return {
                "status": "running" if container.status == "running" else "stopped",
                "container_id": container.id,
                "started_at": container.attrs.get('State', {}).get('StartedAt')
            }
        except docker.errors.NotFound:
            pass
    return {"status": "stopped", "container_id": None, "started_at": None}
