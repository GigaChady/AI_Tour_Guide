package ai.tour.guide.domain.playback

import androidx.media3.common.ForwardingPlayer
import androidx.media3.common.Player

class NavigatingPlayer(
    player: Player,
    private val onNext: () -> Unit,
    private val onPrevious: () -> Unit,
) : ForwardingPlayer(player) {

    override fun getAvailableCommands(): Player.Commands = super.getAvailableCommands()
        .buildUpon()
        .addAll(*NAVIGATION_COMMANDS)
        .build()

    override fun isCommandAvailable(command: Int): Boolean =
        command in NAVIGATION_COMMANDS || super.isCommandAvailable(command)

    override fun hasNextMediaItem(): Boolean = true

    override fun hasPreviousMediaItem(): Boolean = true

    override fun seekToNext() = onNext()

    override fun seekToNextMediaItem() = onNext()

    override fun seekToPrevious() = onPrevious()

    override fun seekToPreviousMediaItem() = onPrevious()

    override fun prepare() {
        if (currentMediaItem?.mediaId?.startsWith(LOADING_MEDIA_ID_PREFIX) == true) {
            return
        }
        super.prepare()
    }

    companion object {
        const val LOADING_MEDIA_ID_PREFIX = "loading:"

        private val NAVIGATION_COMMANDS = intArrayOf(
            COMMAND_SEEK_TO_NEXT,
            COMMAND_SEEK_TO_NEXT_MEDIA_ITEM,
            COMMAND_SEEK_TO_PREVIOUS,
            COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
        )
    }
}
