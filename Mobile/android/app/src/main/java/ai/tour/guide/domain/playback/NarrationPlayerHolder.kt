package ai.tour.guide.domain.playback

import android.content.Context
import androidx.annotation.MainThread
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.exoplayer.ExoPlayer
import org.koin.core.annotation.Singleton

@Singleton
class NarrationPlayerHolder(private val context: Context) {
    private var player: ExoPlayer? = null

    @MainThread
    fun get(): ExoPlayer = player ?: ExoPlayer.Builder(context)
        .setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(C.USAGE_MEDIA)
                .setContentType(C.AUDIO_CONTENT_TYPE_SPEECH)
                .build(), true
        )
        .setHandleAudioBecomingNoisy(true)
        .setWakeMode(C.WAKE_MODE_LOCAL)
        .build().also { player = it }

    @MainThread
    fun release() {
        player?.release(); player = null
    }
}