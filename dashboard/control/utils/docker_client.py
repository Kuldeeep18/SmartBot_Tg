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

def launch_bot_container(token: str, owner_id: str, enabled_plugins: list) -> dict:
    hash_id = get_bot_hash(token)
    container_name = f"anjani-bot-{hash_id}"
    
    try:
        container = client.containers.get(container_name)
        if container.status == 'running':
            return {
                "success": True, 
                "message": "Bot is already running", 
                "container_id": container.id
            }
        container.remove(force=True)
    except docker.errors.NotFound:
        pass
        
    api_id = os.getenv('API_ID', '')
    api_hash = os.getenv('API_HASH', '')
    base_db_uri = os.getenv('DB_URI_TEMPLATE', 'mongodb://localhost:27017')
    
    bot_db_uri = base_db_uri.replace('{HASH}', hash_id) if '{HASH}' in base_db_uri else f"{base_db_uri}/anjani_bot_{hash_id}"
    enabled_plugins_env = ";".join(enabled_plugins)
    
    environment = {
        "API_ID": api_id,
        "API_HASH": api_hash,
        "BOT_TOKEN": token,
        "OWNER_ID": owner_id,
        "DB_URI": bot_db_uri,
        "ENABLED_PLUGINS": enabled_plugins_env
    }
    
    network = os.getenv('DOCKER_NETWORK', 'bridge')
    
    container = client.containers.run(
        image="anjani",
        name=container_name,
        environment=environment,
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        network=network
    )
    
    return {
        "success": True, 
        "message": "Bot container started successfully", 
        "container_id": container.id
    }

def stop_bot_container(token: str) -> dict:
    hash_id = get_bot_hash(token)
    container_name = f"anjani-bot-{hash_id}"
    try:
        container = client.containers.get(container_name)
        container.stop()
        container.remove(force=True)
        return {"success": True, "message": "Bot container stopped and removed"}
    except docker.errors.NotFound:
        return {"success": True, "message": "Bot was already stopped"}

def get_bot_container_status(token: str) -> dict:
    hash_id = get_bot_hash(token)
    container_name = f"anjani-bot-{hash_id}"
    try:
        container = client.containers.get(container_name)
        return {
            "status": "running" if container.status == "running" else "stopped",
            "container_id": container.id,
            "started_at": container.attrs.get('State', {}).get('StartedAt')
        }
    except docker.errors.NotFound:
        return {"status": "stopped", "container_id": None, "started_at": None}
