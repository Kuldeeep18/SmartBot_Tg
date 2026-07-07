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

def landing(request):
    return render(request, 'control/landing.html')

def login_view(request):
    return render(request, 'control/login.html')

def home(request):
    return render(request, 'control/index.html')

@csrf_exempt
def launch_bot_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        bot_type = data.get('type', 'anjani').strip()
        username = data.get('username', '').strip()
        display_name = data.get('displayName', '').strip()
        
        hash_id = data.get('hash', '').strip()
        db = get_db()
        
        if hash_id and not token:
            bot_data = db.bots.find_one({'_id': hash_id})
            if not bot_data:
                return JsonResponse({'error': 'Bot configuration not found'}, status=404)
            token = decrypt(bot_data['encryptedToken'])
            if not username:
                username = bot_data.get('username', '')
            if not display_name:
                display_name = bot_data.get('displayName', '')
        else:
            if not token:
                return JsonResponse({'error': 'Missing Bot Token'}, status=400)
            hash_id = get_bot_hash(token)
            
        # 1. Setup specific configurations per type
        if bot_type == 'anjani':
            owner_id = data.get('ownerId', '').strip()
            if not owner_id and hash_id:
                bot_data = db.bots.find_one({'_id': hash_id})
                if bot_data:
                    owner_id = bot_data.get('ownerId', '').strip()
                    
            enabled_plugins = data.get('enabledPlugins', [])
            
            if not owner_id or not isinstance(enabled_plugins, list):
                return JsonResponse({'error': 'Missing required fields: ownerId, enabledPlugins'}, status=400)
                
            config = {
                'ownerId': owner_id,
                'enabledPlugins': enabled_plugins
            }
            
            # 2. Launch Docker Container
            result = launch_bot_container(token, bot_type, config)
            
            # 3. Save to database
            db.bots.update_one(
                {'_id': hash_id},
                {
                    '$set': {
                        'type': bot_type,
                        'username': username,
                        'displayName': display_name,
                        'encryptedToken': encrypt(token),
                        'ownerId': owner_id,
                        'enabledPlugins': enabled_plugins,
                        'status': 'running',
                        'updatedAt': datetime.utcnow()
                    }
                },
                upsert=True
            )
            
        elif bot_type == 'ai_pdf_chat':
            # AI PDF Chatbot (RAG)
            bot_data = db.bots.find_one({'_id': hash_id}) or {}
            
            supabase_url = data.get('supabaseUrl', '').strip() or bot_data.get('supabaseUrl', '').strip()
            supabase_key = data.get('supabaseKey', '').strip()
            if not supabase_key and 'encryptedSupabaseKey' in bot_data:
                supabase_key = decrypt(bot_data['encryptedSupabaseKey'])
                
            llm_provider = data.get('llmProvider', '').strip() or bot_data.get('llmProvider', 'openai').strip()
            llm_model = data.get('llmModel', '').strip() or bot_data.get('llmModel', 'gpt-4o-mini').strip()
            embedding_model = data.get('embeddingModel', '').strip() or bot_data.get('embeddingModel', 'models/gemini-embedding-001').strip()
            
            llm_api_key = data.get('llmApiKey', '').strip()
            if not llm_api_key and 'encryptedLlmApiKey' in bot_data:
                llm_api_key = decrypt(bot_data['encryptedLlmApiKey'])
            
            chunk_size_raw = data.get('chunkSize')
            chunk_size = int(chunk_size_raw) if chunk_size_raw not in [None, ''] else bot_data.get('chunkSize', 1000)
            
            chunk_overlap_raw = data.get('chunkOverlap')
            chunk_overlap = int(chunk_overlap_raw) if chunk_overlap_raw not in [None, ''] else bot_data.get('chunkOverlap', 200)
            
            retriever_k_raw = data.get('retrieverK')
            retriever_k = int(retriever_k_raw) if retriever_k_raw not in [None, ''] else bot_data.get('retrieverK', 10)
                
            config = {
                'supabaseUrl': supabase_url,
                'supabaseKey': supabase_key,
                'llmProvider': llm_provider,
                'llmModel': llm_model,
                'embeddingModel': embedding_model,
                'llmApiKey': llm_api_key,
                'chunkSize': chunk_size,
                'chunkOverlap': chunk_overlap,
                'retrieverK': retriever_k
            }
            
            # 2. Launch Docker Container
            result = launch_bot_container(token, bot_type, config)
            
            # 3. Save to database
            db.bots.update_one(
                {'_id': hash_id},
                {
                    '$set': {
                        'type': bot_type,
                        'username': username,
                        'displayName': display_name,
                        'encryptedToken': encrypt(token),
                        'supabaseUrl': supabase_url,
                        'encryptedSupabaseKey': encrypt(supabase_key),
                        'llmProvider': llm_provider,
                        'llmModel': llm_model,
                        'embeddingModel': embedding_model,
                        'encryptedLlmApiKey': encrypt(llm_api_key),
                        'chunkSize': chunk_size,
                        'chunkOverlap': chunk_overlap,
                        'retrieverK': retriever_k,
                        'enabledPlugins': [],
                        'status': 'running',
                        'updatedAt': datetime.utcnow()
                    }
                },
                upsert=True
            )
        else:
            # GitHub PR Bot
            bot_data = db.bots.find_one({'_id': hash_id}) or {}
            
            gemini_api_key = data.get('geminiApiKey', '').strip()
            if not gemini_api_key and 'encryptedGeminiKey' in bot_data:
                gemini_api_key = decrypt(bot_data['encryptedGeminiKey'])
                
            github_token = data.get('githubToken', '').strip()
            if not github_token and 'encryptedGithubToken' in bot_data:
                github_token = decrypt(bot_data['encryptedGithubToken'])
                
            max_repo_size_raw = data.get('maxRepoSize')
            max_repo_size = int(max_repo_size_raw) if max_repo_size_raw not in [None, ''] else bot_data.get('maxRepoSize', 100)
            
            github_client_id = data.get('githubClientId', '').strip() or bot_data.get('githubClientId', '').strip()
            
            github_client_secret = data.get('githubClientSecret', '').strip()
            if not github_client_secret and 'encryptedGithubClientSecret' in bot_data:
                github_client_secret = decrypt(bot_data['encryptedGithubClientSecret'])
                
            oauth_redirect_url = data.get('oauthRedirectUrl', '').strip() or bot_data.get('oauthRedirectUrl', '').strip()

            config = {
                'geminiApiKey': gemini_api_key,
                'githubToken': github_token,
                'maxRepoSize': max_repo_size,
                'githubClientId': github_client_id,
                'githubClientSecret': github_client_secret,
                'oauthRedirectUrl': oauth_redirect_url
            }

            # 2. Launch Docker Container
            result = launch_bot_container(token, bot_type, config)

            # 3. Save to database
            db.bots.update_one(
                {'_id': hash_id},
                {
                    '$set': {
                        'type': bot_type,
                        'username': username,
                        'displayName': display_name,
                        'encryptedToken': encrypt(token),
                        'encryptedGeminiKey': encrypt(gemini_api_key),
                        'encryptedGithubToken': encrypt(github_token),
                        'maxRepoSize': max_repo_size,
                        'githubClientId': github_client_id,
                        'encryptedGithubClientSecret': encrypt(github_client_secret),
                        'oauthRedirectUrl': oauth_redirect_url,
                        'enabledPlugins': [],
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
    
    # 1. Handle POST (Stop / Delete Bot)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hash_id = data.get('hash', '').strip()
            token = data.get('token', '').strip()
            action = data.get('action', '').strip()
            
            if action not in ['stop', 'delete', 'start']:
                return JsonResponse({'error': 'Invalid action'}, status=400)
                
            target_hash = hash_id if hash_id else get_bot_hash(token)
            
            bot_data = db.bots.find_one({'_id': target_hash})
            if not bot_data:
                return JsonResponse({'error': 'Bot configuration not found'}, status=404)
                
            raw_token = decrypt(bot_data['encryptedToken'])
            
            if action == 'delete':
                try:
                    stop_bot_container(raw_token)
                except Exception:
                    pass
                db.bots.delete_one({'_id': target_hash})
                return JsonResponse({'success': True, 'message': 'Bot deleted successfully'})
            elif action == 'stop':
                try:
                    stop_bot_container(raw_token)
                except Exception:
                    pass
                db.bots.update_one(
                    {'_id': target_hash},
                    {'$set': {'status': 'stopped', 'updatedAt': datetime.utcnow()}}
                )
                return JsonResponse({'success': True, 'message': 'Bot stopped successfully'})
            elif action == 'start':
                bot_type = bot_data.get('type', 'anjani')
                config = {}
                if bot_type == 'anjani':
                    config = {
                        'ownerId': bot_data.get('ownerId', ''),
                        'enabledPlugins': bot_data.get('enabledPlugins', [])
                    }
                elif bot_type == 'ai_pdf_chat':
                    config = {
                        'supabaseUrl': bot_data.get('supabaseUrl', ''),
                        'supabaseKey': decrypt(bot_data['encryptedSupabaseKey']) if 'encryptedSupabaseKey' in bot_data else '',
                        'llmProvider': bot_data.get('llmProvider', 'openai'),
                        'llmModel': bot_data.get('llmModel', ''),
                        'embeddingModel': bot_data.get('embeddingModel', ''),
                        'llmApiKey': decrypt(bot_data['encryptedLlmApiKey']) if 'encryptedLlmApiKey' in bot_data else '',
                        'chunkSize': bot_data.get('chunkSize', 1000),
                        'chunkOverlap': bot_data.get('chunkOverlap', 200),
                        'retrieverK': bot_data.get('retrieverK', 10)
                    }
                else:
                    config = {
                        'geminiApiKey': decrypt(bot_data['encryptedGeminiKey']) if 'encryptedGeminiKey' in bot_data else '',
                        'githubToken': decrypt(bot_data['encryptedGithubToken']) if 'encryptedGithubToken' in bot_data else '',
                        'maxRepoSize': bot_data.get('maxRepoSize', 100),
                        'githubClientId': bot_data.get('githubClientId', ''),
                        'githubClientSecret': decrypt(bot_data['encryptedGithubClientSecret']) if 'encryptedGithubClientSecret' in bot_data else '',
                        'oauthRedirectUrl': bot_data.get('oauthRedirectUrl', '')
                    }
                
                # Launch Bot container
                launch_bot_container(raw_token, bot_type, config)
                db.bots.update_one(
                    {'_id': target_hash},
                    {'$set': {'status': 'running', 'updatedAt': datetime.utcnow()}}
                )
                return JsonResponse({'success': True, 'message': 'Bot started successfully'})
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
                    bot_record = {
                        'hash': b['_id'],
                        'type': b.get('type', 'anjani'),
                        'status': b.get('status', 'stopped'),
                        'username': b.get('username', ''),
                        'displayName': b.get('displayName', ''),
                        'ownerId': b.get('ownerId', ''),
                        'enabledPlugins': b.get('enabledPlugins', []),
                        'supabaseUrl': b.get('supabaseUrl', ''),
                        'supabaseKey': decrypt(b['encryptedSupabaseKey']) if 'encryptedSupabaseKey' in b else '',
                        'llmProvider': b.get('llmProvider', 'openai'),
                        'llmModel': b.get('llmModel', ''),
                        'embeddingModel': b.get('embeddingModel', ''),
                        'llmApiKey': decrypt(b['encryptedLlmApiKey']) if 'encryptedLlmApiKey' in b else '',
                        'chunkSize': b.get('chunkSize', 1000),
                        'chunkOverlap': b.get('chunkOverlap', 200),
                        'retrieverK': b.get('retrieverK', 10),
                        'geminiApiKey': decrypt(b['encryptedGeminiKey']) if 'encryptedGeminiKey' in b else '',
                        'githubToken': decrypt(b['encryptedGithubToken']) if 'encryptedGithubToken' in b else '',
                        'maxRepoSize': b.get('maxRepoSize', 100),
                        'githubClientId': b.get('githubClientId', ''),
                        'githubClientSecret': decrypt(b['encryptedGithubClientSecret']) if 'encryptedGithubClientSecret' in b else '',
                        'oauthRedirectUrl': b.get('oauthRedirectUrl', ''),
                        'updatedAt': b.get('updatedAt', datetime.utcnow()).isoformat() if isinstance(b.get('updatedAt'), datetime) else str(b.get('updatedAt'))
                    }
                    clean_bots.append(bot_record)
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
                
            response_data = {
                'hash': target_hash,
                'type': bot_data.get('type', 'anjani'),
                'status': live_status['status'],
                'username': bot_data.get('username', ''),
                'displayName': bot_data.get('displayName', ''),
                'startedAt': live_status.get('started_at'),
            }
            
            if bot_data.get('type', 'anjani') == 'anjani':
                response_data.update({
                    'ownerId': bot_data.get('ownerId', ''),
                    'enabledPlugins': bot_data.get('enabledPlugins', []),
                })
            elif bot_data.get('type', 'anjani') == 'ai_pdf_chat':
                response_data.update({
                    'supabaseUrl': bot_data.get('supabaseUrl', ''),
                    'supabaseKey': decrypt(bot_data['encryptedSupabaseKey']) if 'encryptedSupabaseKey' in bot_data else '',
                    'llmProvider': bot_data.get('llmProvider', 'openai'),
                    'llmModel': bot_data.get('llmModel', ''),
                    'embeddingModel': bot_data.get('embeddingModel', ''),
                    'llmApiKey': decrypt(bot_data['encryptedLlmApiKey']) if 'encryptedLlmApiKey' in bot_data else '',
                    'chunkSize': bot_data.get('chunkSize', 1000),
                    'chunkOverlap': bot_data.get('chunkOverlap', 200),
                    'retrieverK': bot_data.get('retrieverK', 10)
                })
            else:
                response_data.update({
                    'geminiApiKey': decrypt(bot_data['encryptedGeminiKey']) if 'encryptedGeminiKey' in bot_data else '',
                    'githubToken': decrypt(bot_data['encryptedGithubToken']) if 'encryptedGithubToken' in bot_data else '',
                    'maxRepoSize': bot_data.get('maxRepoSize', 100),
                    'githubClientId': bot_data.get('githubClientId', ''),
                    'githubClientSecret': decrypt(bot_data['encryptedGithubClientSecret']) if 'encryptedGithubClientSecret' in bot_data else '',
                    'oauthRedirectUrl': bot_data.get('oauthRedirectUrl', '')
                })
                
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def log_error(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("\n" + "="*50)
            print("CLIENT JS ERROR:")
            print(f"Message: {data.get('message')}")
            print(f"Source: {data.get('source')} (Line {data.get('lineno')}, Col {data.get('colno')})")
            print(f"Stack Trace:\n{data.get('error')}")
            print("="*50 + "\n")
        except Exception as e:
            print("Error logging failed:", e)
    return JsonResponse({'status': 'ok'})
