package ai.tour.guide.ui.screens.main

import ai.tour.guide.ui.components.input.SaveButton
import ai.tour.guide.ui.sharedFragments.preferences.UserPreferenceFragment
import ai.tour.guide.ui.sharedFragments.preferences.UserPreferenceFragmentViewModel
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleStartEffect
import org.koin.compose.viewmodel.koinViewModel

@Composable
fun ProfilePreferencesScreen(
    modifier: Modifier = Modifier,
    viewModel: UserPreferenceFragmentViewModel = koinViewModel()
) {
    LifecycleStartEffect(Unit) {
        viewModel.onStart()
        onStopOrDispose { }
    }

    Surface(
        modifier = modifier
            .fillMaxSize()
            .testTag("profile_screen"),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(8.dp)
        ) {
            UserPreferenceFragment(
                modifier = Modifier.weight(1f),
                viewModel = viewModel
            )

            // Save button component
            SaveButton(
                onClick = { viewModel.onSavePreferencesClicked() }
            )
        }
    }
}
