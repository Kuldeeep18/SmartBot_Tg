import Docker from 'dockerode'
import os from 'os'
import crypto from 'crypto'

const isWindows = os.platform() === 'win32'
const docker = new Docker(
  isWindows
    ? { socketPath: '//./pipe/docker_engine' }
    : { socketPath: '/var/run/docker.sock' }
)

// Generate a deterministic short hash from the bot token for container naming and DB naming
export function getBotHash(token: string): string {
  return crypto.createHash('sha256').update(token).digest('hex').substring(0, 12)
}

export interface BotLaunchOptions {
  token: string
  ownerId: string
  enabledPlugins: string[] // e.g. ['muting', 'welcome']
}

export async function launchBotContainer(options: BotLaunchOptions) {
  const hash = getBotHash(options.token)
  const containerName = `anjani-bot-${hash}`

  // Check if container already exists
  try {
    const existing = docker.getContainer(containerName)
    const info = await existing.inspect()
    if (info.State.Running) {
      return { success: true, message: 'Bot is already running', containerId: info.Id }
    }
    // If exists but stopped, remove it first to recreate with new settings
    await existing.remove({ force: true })
  } catch {
    // Container does not exist, safe to proceed
  }

  const apiId = process.env.API_ID || ''
  const apiHash = process.env.API_HASH || ''
  const baseDbUri = process.env.DB_URI_TEMPLATE || 'mongodb://localhost:27017'
  
  // Format the DB_URI specifically for this bot database
  const botDbUri = baseDbUri.includes('{HASH}')
    ? baseDbUri.replace('{HASH}', hash)
    : `${baseDbUri}/anjani_bot_${hash}`

  const enabledPluginsEnv = options.enabledPlugins.join(';')

  // Define environment variables for the bot container
  const env = [
    `API_ID=${apiId}`,
    `API_HASH=${apiHash}`,
    `BOT_TOKEN=${options.token}`,
    `OWNER_ID=${options.ownerId}`,
    `DB_URI=${botDbUri}`,
    `ENABLED_PLUGINS=${enabledPluginsEnv}`,
  ]

  // Create and start the container
  const container = await docker.createContainer({
    Image: 'anjani',
    name: containerName,
    Env: env,
    HostConfig: {
      RestartPolicy: { Name: 'unless-stopped' },
      // Optional: Add to same network as MongoDB if running in the monorepo compose network
      NetworkMode: process.env.DOCKER_NETWORK || 'bridge',
    },
  })

  await container.start()
  const info = await container.inspect()

  return {
    success: true,
    message: 'Bot container started successfully',
    containerId: info.Id,
  }
}

export async function stopBotContainer(token: string) {
  const hash = getBotHash(token)
  const containerName = `anjani-bot-${hash}`

  try {
    const container = docker.getContainer(containerName)
    await container.stop()
    await container.remove({ force: true })
    return { success: true, message: 'Bot container stopped and removed' }
  } catch (err) {
    if (err && typeof err === 'object' && 'statusCode' in err && err.statusCode === 404) {
      return { success: true, message: 'Bot was already stopped' }
    }
    throw err
  }
}

export async function getBotContainerStatus(token: string) {
  const hash = getBotHash(token)
  const containerName = `anjani-bot-${hash}`

  try {
    const container = docker.getContainer(containerName)
    const info = await container.inspect()
    return {
      status: info.State.Running ? 'running' : 'stopped',
      containerId: info.Id,
      startedAt: info.State.StartedAt,
    }
  } catch (err) {
    if (err && typeof err === 'object' && 'statusCode' in err && err.statusCode === 404) {
      return { status: 'stopped', containerId: null, startedAt: null }
    }
    throw err
  }
}
