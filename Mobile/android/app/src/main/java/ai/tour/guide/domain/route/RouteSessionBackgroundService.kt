package ai.tour.guide.domain.route

import ai.tour.guide.domain.playback.NarrationPlayerHolder
import ai.tour.guide.domain.playback.NavigatingPlayer
import ai.tour.guide.notifications.NotificationChannels
import android.Manifest
import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.annotation.OptIn
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.DefaultMediaNotificationProvider
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import androidx.media3.session.MediaStyleNotificationHelper
import androidx.media3.session.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.koin.android.ext.android.inject
import ai.tour.guide.R as AppR

class RouteSessionBackgroundService :
    MediaSessionService() {
    private val holder: NarrationPlayerHolder by inject()
    private val routeService: RouteService by inject()
    private val narration: RouteNarrationPlaybackService by inject()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var session: MediaSession? = null
    private var routeStarted = false

    @OptIn(UnstableApi::class)
    override fun onCreate() {
        super.onCreate()
        setMediaNotificationProvider(
            DefaultMediaNotificationProvider.Builder(this)
                .setChannelId(NotificationChannels.ROUTE)
                .setNotificationIdProvider { NotificationChannels.NOTIFICATION_ID }
                .build()
                .apply { setSmallIcon(R.drawable.media3_notification_small_icon) }
        )
        val sessionPlayer = NavigatingPlayer(
            holder.get(),
            onNext = narration::skipToNext,
            onPrevious = narration::skipToPrevious
        )
        setShowNotificationForIdlePlayer(SHOW_NOTIFICATION_FOR_IDLE_PLAYER_ALWAYS)
        val s = MediaSession.Builder(this, sessionPlayer)
            .setSessionActivity(openAppPendingIntent())
            .build()
        session = s
        addSession(s)
    }

    override fun onGetSession(info: MediaSession.ControllerInfo) = session

    @SuppressLint("MissingPermission")
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        enterForeground()
        if (!routeStarted) {
            routeStarted = true
            scope.launch {
                routeLifecycleMutex.withLock { routeService.onStart() }
                withContext(Dispatchers.Main) { narration.startNavigation() }
            }
        }
        return super.onStartCommand(intent, flags, startId)
    }

    override fun onUpdateNotification(session: MediaSession, startInForegroundRequired: Boolean) {
        super.onUpdateNotification(session, true)
    }

    @OptIn(UnstableApi::class)
    private fun enterForeground() {
        NotificationChannels.create(applicationContext)
        val n = NotificationCompat.Builder(this, NotificationChannels.ROUTE)
            .setContentTitle(getString(AppR.string.audio_player_preparing_tour_message))
            .setOngoing(true)
            .setContentIntent(openAppPendingIntent())
            .setStyle(MediaStyleNotificationHelper.MediaStyle(session!!))
            .apply { setSmallIcon(R.drawable.media3_notification_small_icon) }
            .build()
        val type = when {
            Build.VERSION.SDK_INT < Build.VERSION_CODES.Q -> 0
            hasLocationPermission() -> ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION or
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK

            else -> ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
        }
        ServiceCompat.startForeground(this, NotificationChannels.NOTIFICATION_ID, n, type)
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
    }

    private fun hasLocationPermission(): Boolean =
        listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            .any { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }

    override fun onDestroy() {
        scope.cancel()
        routeStarted = false
        session?.release(); session = null
        narration.detachPlayer()
        holder.release()
        teardownScope.launch {
            routeLifecycleMutex.withLock { routeService.onDestroy() }
        }
        super.onDestroy()
    }

    private companion object {
        val teardownScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        val routeLifecycleMutex = Mutex()
    }

    private fun openAppPendingIntent(): PendingIntent {
        val intent = packageManager.getLaunchIntentForPackage(packageName)!!
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        return PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}