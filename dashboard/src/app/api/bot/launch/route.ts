import { NextResponse } from 'next/server'
import { connectToDatabase } from '@/lib/db'
import { launchBotContainer, getBotHash } from '@/lib/docker'
import { encrypt } from '@/lib/crypto'

interface BotSchema {
  _id: string
  encryptedToken: string
  ownerId: string
  enabledPlugins: string[]
  status: string
  updatedAt: Date
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { token, ownerId, enabledPlugins } = body

    if (!token || !ownerId || !Array.isArray(enabledPlugins)) {
      return NextResponse.json(
        { error: 'Missing required parameters: token, ownerId, enabledPlugins' },
        { status: 400 }
      )
    }

    const hash = getBotHash(token)
    const db = await connectToDatabase()

    // 1. Launch the docker container for the bot
    const result = await launchBotContainer({
      token,
      ownerId,
      enabledPlugins,
    })

    // 2. Save bot configuration state in MongoDB
    await db.collection<BotSchema>('bots').updateOne(
      { _id: hash },
      {
        $set: {
          encryptedToken: encrypt(token),
          ownerId,
          enabledPlugins,
          status: 'running',
          updatedAt: new Date(),
        },
      },
      { upsert: true }
    )

    return NextResponse.json({
      success: true,
      message: result.message,
      hash,
    })
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Internal server error'
    console.error('Launch Error:', error)
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    )
  }
}
