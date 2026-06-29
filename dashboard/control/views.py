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
        
        if not token:
            return JsonResponse({'error': 'Missing Bot Token'}, status=400)
            
        hash_id = get_bot_hash(token)
        db = get_db()
        
        # 1. Setup specific configurations per type
        if bot_type == 'anjani':
            owner_id = data.get('ownerId', '').strip()
            enabled_plugins = data.get('enabledPlugins', [])
            
            if not owner_id or not isinstance(enabled_plugins, list):
                return JsonResponse({'error': 'Missing required fields for Anjani: ownerId, enabledPlugins'}, status=400)
                
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
            supabase_url = data.get('supabaseUrl', '').strip()
            supabase_key = data.get('supabaseKey', '').strip()
            llm_provider = data.get('llmProvider', 'openai').strip()
            llm_model = data.get('llmModel', 'gpt-4o-mini').strip()
            embedding_model = data.get('embeddingModel', 'text-embedding-3-small').strip()
            llm_api_key = data.get('llmApiKey', '').strip()
            chunk_size = int(data.get('chunkSize', 1000))
            chunk_overlap = int(data.get('chunkOverlap', 200))
            retriever_k = int(data.get('retrieverK', 10))
            
            if not supabase_url or not supabase_key or not llm_api_key:
                return JsonResponse({'error': 'Missing required fields for RAG: supabaseUrl, supabaseKey, llmApiKey'}, status=400)
                
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
                        'status': 'running',
                        'updatedAt': datetime.utcnow()
                    }
                },
                upsert=True
            )
        else:
            # GitHub PR Bot
            gemini_api_key = data.get('geminiApiKey', '').strip()
            github_token = data.get('githubToken', '').strip()
            max_repo_size = int(data.get('maxRepoSize', 100))
            github_client_id = data.get('githubClientId', '').strip()
            github_client_secret = data.get('githubClientSecret', '').strip()
            oauth_redirect_url = data.get('oauthRedirectUrl', '').strip()

            if not gemini_api_key:
                return JsonResponse({'error': 'Missing Gemini API Key'}, status=400)

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
                        'encryptedToken': encrypt(token),
                        'encryptedGeminiKey': encrypt(gemini_api_key),
                        'encryptedGithubToken': encrypt(github_token),
                        'maxRepoSize': max_repo_size,
                        'githubClientId': github_client_id,
                        'encryptedGithubClientSecret': encrypt(github_client_secret),
                        'oauthRedirectUrl': oauth_redirect_url,
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
            
            # Update database status
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
                    bot_type = b.get('type', 'anjani')
                    bot_record = {
                        'hash': b['_id'],
                        'type': bot_type,
                        'status': b.get('status', 'stopped'),
                        'updatedAt': b.get('updatedAt', datetime.utcnow()).isoformat() if isinstance(b.get('updatedAt'), datetime) else str(b.get('updatedAt'))
                    }
                    
                    if bot_type == 'anjani':
                        bot_record.update({
                            'ownerId': b.get('ownerId', ''),
                            'enabledPlugins': b.get('enabledPlugins', [])
                        })
                    elif bot_type == 'ai_pdf_chat':
                        bot_record.update({
                            'supabaseUrl': b.get('supabaseUrl', ''),
                            'supabaseKey': decrypt(b['encryptedSupabaseKey']) if 'encryptedSupabaseKey' in b else '',
                            'llmProvider': b.get('llmProvider', 'openai'),
                            'llmModel': b.get('llmModel', ''),
                            'embeddingModel': b.get('embeddingModel', ''),
                            'llmApiKey': decrypt(b['encryptedLlmApiKey']) if 'encryptedLlmApiKey' in b else '',
                            'chunkSize': b.get('chunkSize', 1000),
                            'chunkOverlap': b.get('chunkOverlap', 200),
                            'retrieverK': b.get('retrieverK', 10)
                        })
                    else:
                        # github_pr_bot
                        bot_record.update({
                            'geminiApiKey': decrypt(b['encryptedGeminiKey']) if 'encryptedGeminiKey' in b else '',
                            'githubToken': decrypt(b['encryptedGithubToken']) if 'encryptedGithubToken' in b else '',
                            'maxRepoSize': b.get('maxRepoSize', 100),
                            'githubClientId': b.get('githubClientId', ''),
                            'githubClientSecret': decrypt(b['encryptedGithubClientSecret']) if 'encryptedGithubClientSecret' in b else '',
                            'oauthRedirectUrl': b.get('oauthRedirectUrl', '')
                        })
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
