import json
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .utils.db import get_db
from .utils.crypto import encrypt, decrypt
from .utils.docker_client import (
    launch_bot_container, 
    stop_bot_container, 
    get_bot_container_status, 
    get_bot_hash
)

def home(request):
    return render(request, 'control/index.html')

@csrf_exempt
def launch_bot_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        owner_id = data.get('ownerId', '').strip()
        enabled_plugins = data.get('enabledPlugins', [])
        
        if not token or not owner_id or not isinstance(enabled_plugins, list):
            return JsonResponse({'error': 'Missing required fields: token, ownerId, enabledPlugins'}, status=400)
            
        hash_id = get_bot_hash(token)
        db = get_db()
        
        # 1. Launch Docker Container
        result = launch_bot_container(token, owner_id, enabled_plugins)
        
        # 2. Persist configuration in MongoDB
        db.bots.update_one(
            {'_id': hash_id},
            {
                '$set': {
                    'encryptedToken': encrypt(token),
                    'ownerId': owner_id,
                    'enabledPlugins': enabled_plugins,
                    'status': 'running',
                    'updatedAt': datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return JsonResponse({
            'success': True,
            'message': result.get('message', 'Bot container started'),
            'hash': hash_id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def status_bot_api(request):
    db = get_db()
    
    # 1. Handle POST (Stop Bot)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hash_id = data.get('hash', '').strip()
            token = data.get('token', '').strip()
            action = data.get('action', '').strip()
            
            if action != 'stop':
                return JsonResponse({'error': 'Invalid action'}, status=400)
                
            target_hash = hash_id if hash_id else get_bot_hash(token)
            
            bot_data = db.bots.find_one({'_id': target_hash})
            if not bot_data:
                return JsonResponse({'error': 'Bot configuration not found'}, status=404)
                
            raw_token = decrypt(bot_data['encryptedToken'])
            
            # Stop container
            stop_bot_container(raw_token)
            
            # Update database status to stopped
            db.bots.update_one(
                {'_id': target_hash},
                {'$set': {'status': 'stopped', 'updatedAt': datetime.utcnow()}}
            )
            
            return JsonResponse({'success': True, 'message': 'Bot stopped successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    # 2. Handle GET (Check status/list)
    elif request.method == 'GET':
        try:
            hash_id = request.GET.get('hash', '').strip()
            token = request.GET.get('token', '').strip()
            
            if not hash_id and not token:
                # Retrieve list of all bots
                bots = list(db.bots.find())
                clean_bots = []
                for b in bots:
                    clean_bots.append({
                        'hash': b['_id'],
                        'ownerId': b.get('ownerId', ''),
                        'enabledPlugins': b.get('enabledPlugins', []),
                        'status': b.get('status', 'stopped'),
                        'updatedAt': b.get('updatedAt', datetime.utcnow()).isoformat() if isinstance(b.get('updatedAt'), datetime) else str(b.get('updatedAt'))
                    })
                return JsonResponse({'bots': clean_bots})
                
            target_hash = hash_id if hash_id else get_bot_hash(token)
            bot_data = db.bots.find_one({'_id': target_hash})
            
            if not bot_data:
                return JsonResponse({'status': 'not_found'})
                
            raw_token = decrypt(bot_data['encryptedToken'])
            live_status = get_bot_container_status(raw_token)
            
            # Sync DB status if it differs
            if live_status['status'] != bot_data.get('status'):
                db.bots.update_one(
                    {'_id': target_hash},
                    {'$set': {'status': live_status['status']}}
                )
                
            return JsonResponse({
                'hash': target_hash,
                'ownerId': bot_data.get('ownerId', ''),
                'enabledPlugins': bot_data.get('enabledPlugins', []),
                'status': live_status['status'],
                'startedAt': live_status.get('started_at')
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Method not allowed'}, status=405)
