import { NextResponse } from 'next/server'
import { connectToDatabase } from '@/lib/db'
import { stopBotContainer, getBotContainerStatus, getBotHash } from '@/lib/docker'
import { decrypt } from '@/lib/crypto'

interface BotSchema {
  _id: string
  encryptedToken: string
  ownerId: string
  enabledPlugins: string[]
  status: string
  updatedAt: Date
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const hash = searchParams.get('hash')
    const token = searchParams.get('token')

    if (!hash && !token) {
      // If neither is specified, return all bots registered in DB
      const db = await connectToDatabase()
      const bots = await db.collection<BotSchema>('bots').find().toArray()
      
      // Clean up representation (don't send raw encrypted tokens to client)
      const cleanBots = bots.map(b => ({
        hash: b._id,
        ownerId: b.ownerId,
        enabledPlugins: b.enabledPlugins,
        status: b.status,
        updatedAt: b.updatedAt,
      }))
      
      return NextResponse.json({ bots: cleanBots })
    }

    const targetHash = hash || getBotHash(token!)
    const db = await connectToDatabase()
    const botData = await db.collection<BotSchema>('bots').findOne({ _id: targetHash })

    if (!botData) {
      return NextResponse.json({ status: 'not_found' })
    }

    // Decrypt token to check live container status
    const rawToken = decrypt(botData.encryptedToken)
    const liveStatus = await getBotContainerStatus(rawToken)

    // Sync DB status if it has changed
    if (liveStatus.status !== botData.status) {
      await db.collection<BotSchema>('bots').updateOne(
        { _id: targetHash },
        { $set: { status: liveStatus.status } }
      )
    }

    return NextResponse.json({
      hash: targetHash,
      ownerId: botData.ownerId,
      enabledPlugins: botData.enabledPlugins,
      status: liveStatus.status,
      startedAt: liveStatus.startedAt,
    })
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Internal server error'
    console.error('Status GET Error:', error)
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { hash, token, action } = body

    if (action !== 'stop') {
      return NextResponse.json({ error: 'Invalid action' }, { status: 400 })
    }

    if (!hash && !token) {
      return NextResponse.json({ error: 'Missing hash or token' }, { status: 400 })
    }

    const targetHash = hash || getBotHash(token)
    const db = await connectToDatabase()
    const botData = await db.collection<BotSchema>('bots').findOne({ _id: targetHash })

    if (!botData) {
      return NextResponse.json({ error: 'Bot configuration not found' }, { status: 404 })
    }

    const rawToken = decrypt(botData.encryptedToken)

    // Stop and remove the container
    await stopBotContainer(rawToken)

    // Update database status
    await db.collection<BotSchema>('bots').updateOne(
      { _id: targetHash },
      { $set: { status: 'stopped', updatedAt: new Date() } }
    )

    return NextResponse.json({ success: true, message: 'Bot stopped successfully' })
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Internal server error'
    console.error('Status POST Error:', error)
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    )
  }
}
