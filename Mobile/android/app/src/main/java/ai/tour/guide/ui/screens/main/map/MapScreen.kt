package ai.tour.guide.ui.screens.main.map

import ai.tour.guide.R
import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.CameraPositionState
import com.google.maps.android.compose.Circle
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.MapProperties
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.Polyline
import com.google.maps.android.compose.rememberCameraPositionState
import com.google.maps.android.compose.rememberUpdatedMarkerState
import org.koin.compose.viewmodel.koinViewModel

private object MapConfig {
    val FallbackLocation = LatLng(0.0, 0.0)
    const val InitialZoom = 2f
    const val TrackingZoom = 16f
    const val AnimationDuration = 500

    val PathColor = Color.Blue.copy(alpha = 0.4f)
    const val PathWidth = 12f

    val StartPointFillColor = Color.Blue.copy(alpha = 0.4f)
    val StartPointStrokeColor = Color.DarkGray
    const val StartPointStrokeWidth = 3f
    const val StartPointRadius = 5.0
}

@Composable
fun MapScreen(
    modifier: Modifier = Modifier,
    backStack: NavBackStack<NavKey>? = null,
    viewModel: MapViewModel = koinViewModel()
) {
    val context = LocalContext.current
    val viewState by viewModel.viewStateFlow.collectAsStateWithLifecycle()
    val state = viewState.data

    // Map properties
    var isMapLoaded by remember { mutableStateOf(false) }
    var hasInitiallyFocused by remember { mutableStateOf(false) }
    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(MapConfig.FallbackLocation, MapConfig.InitialZoom)
    }
    val focusLocation = state.userPath.lastOrNull() ?: state.lastKnownLocation
    val properties = MapProperties(
        isMyLocationEnabled = state.isLocationPermissionGranted
    )
    val uiSettings = MapUiSettings(
        myLocationButtonEnabled = state.isLocationPermissionGranted,
        compassEnabled = true
    )

    // Permission launcher
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        viewModel.onLocationPermissionResult(isGranted)
    }

    LifecycleStartEffect(Unit) {
        viewModel.onStart()

        val permissionCheck = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        )
        if (permissionCheck != PackageManager.PERMISSION_GRANTED) {
            permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
        } else {
            viewModel.onLocationPermissionResult(true)
        }

        onStopOrDispose {}
    }

    LaunchedEffect(focusLocation, isMapLoaded) {
        if (!isMapLoaded || focusLocation == null) return@LaunchedEffect

        if (!hasInitiallyFocused) {
            cameraPositionState.move(
                update = CameraUpdateFactory.newLatLngZoom(focusLocation, MapConfig.TrackingZoom)
            )
            hasInitiallyFocused = true
        } else if (state.userPath.isNotEmpty()) {
            cameraPositionState.animate(
                update = CameraUpdateFactory.newLatLngZoom(focusLocation, MapConfig.TrackingZoom),
                durationMs = MapConfig.AnimationDuration
            )
        }
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .testTag("map_screen")
    ) {
        TourGoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = cameraPositionState,
            properties = properties,
            uiSettings = uiSettings,
            state = state,
            onMapLoaded = { isMapLoaded = true }
        )
    }
}

@Composable
private fun TourGoogleMap(
    modifier: Modifier,
    cameraPositionState: CameraPositionState,
    properties: MapProperties,
    uiSettings: MapUiSettings,
    state: MapState,
    onMapLoaded: () -> Unit
) {
    GoogleMap(
        modifier = modifier,
        cameraPositionState = cameraPositionState,
        properties = properties,
        uiSettings = uiSettings,
        onMapLoaded = onMapLoaded
    ) {
        if (state.userPath.isNotEmpty()) {

            // User path
            Polyline(
                points = state.userPath,
                clickable = false,
                color = MapConfig.PathColor,
                width = MapConfig.PathWidth
            )

            // Starting point
            Circle(
                center = state.userPath.first(),
                fillColor = MapConfig.StartPointFillColor,
                strokeColor = MapConfig.StartPointStrokeColor,
                strokeWidth = MapConfig.StartPointStrokeWidth,
                radius = MapConfig.StartPointRadius
            )
        }

        state.visitedStops.forEach { poi ->
            key(poi.id) {
                val markerState = rememberUpdatedMarkerState(position = poi.position)
                Marker(
                    state = markerState,
                    title = poi.title ?: stringResource(R.string.map_visited_stop_title_default),
                    snippet = poi.snippet ?: stringResource(R.string.map_visited_stop_snippet_default)
                )
            }
        }
    }
}
