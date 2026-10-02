package ai.tour.guide.ui.screens.main.appSettings

import ai.tour.guide.R
import ai.tour.guide.data.appSettings.AppSettingsAppThemeType
import ai.tour.guide.data.appSettings.AppSettingsDetailLevelType
import ai.tour.guide.ui.components.input.SaveButton
import ai.tour.guide.ui.components.input.SegmentedButton
import ai.tour.guide.ui.components.settings.PickerSetting
import ai.tour.guide.ui.components.settings.RadioOptionsList
import ai.tour.guide.ui.components.settings.SettingGroupHeader
import ai.tour.guide.ui.components.settings.SettingItemWithTitle
import ai.tour.guide.ui.navigation.Route
import ai.tour.guide.ui.components.onboarding.LoadingOverlay
import ai.tour.guide.ui.components.shared.ToastOnRequestError
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Language
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import androidx.navigation3.runtime.rememberNavBackStack
import org.koin.compose.viewmodel.koinViewModel

@Composable
fun AppSettingsScreen(
    modifier: Modifier = Modifier,
    backStack: NavBackStack<NavKey>? = rememberNavBackStack(),
    viewModel: AppSettingsViewModel = koinViewModel()
) {
    val viewState by viewModel.viewStateFlow.collectAsStateWithLifecycle()
    val state = viewState.data

    LifecycleStartEffect(Unit) {
        viewModel.onStart()
        onStopOrDispose { }
    }

    ToastOnRequestError(viewModel = viewModel)

    Surface(
        modifier = modifier
            .fillMaxSize()
            .testTag("settings_screen"),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier.fillMaxSize()
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(32.dp)
            ) {
                GeneralAppSettingsSection(
                    currentTheme = state.appTheme,
                    onThemeChanged = { viewModel.updateTheme(it) }
                )

                AccountSettingsSection(backStack = backStack)

                TTSSettingsSection(
                    language = state.language,
                    pitch = state.pitch,
                    speed = state.speed,
                    onLanguageChanged = { viewModel.updateLanguage(it) },
                    onPitchChanged = { viewModel.updatePitch(it) },
                    onSpeedChanged = { viewModel.updateSpeed(it) }
                )

                PlaybackSettingsSection(
                    detailLevel = state.detailLevel,
                    autoPlay = state.autoPlay,
                    onDetailLevelChanged = { viewModel.updateDetailLevel(it) },
                    onAutoPlayChanged = { viewModel.updateAutoPlay(it) }
                )
            }

            // Save button component
            SaveButton(
                onClick = { viewModel.onSaveSettingsClicked() }
            )
        }
    }

    LoadingOverlay(isVisible = viewState.isLoading)
}

@Composable
fun GeneralAppSettingsSection(
    currentTheme: AppSettingsAppThemeType,
    onThemeChanged: (AppSettingsAppThemeType) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        SettingGroupHeader(
            title = stringResource(R.string.app_settings_general_section_header),
            subtitle = stringResource(R.string.app_settings_general_section_body)
        )
        SettingItemWithTitle(
            title = stringResource(R.string.app_settings_general_color_scheme_header)
        ) {
            val themeOptions = AppSettingsAppThemeType.entries.map { theme ->
                when (theme) {
                    AppSettingsAppThemeType.SYSTEM -> stringResource(R.string.app_settings_general_color_scheme_option_auto)
                    AppSettingsAppThemeType.DARK -> stringResource(R.string.app_settings_general_color_scheme_option_dark)
                    AppSettingsAppThemeType.LIGHT -> stringResource(R.string.app_settings_general_color_scheme_option_light)
                }
            }

            RadioOptionsList(
                options = themeOptions,
                selectedIndex = currentTheme.ordinal,
                onOptionSelected = { index ->
                    // Get theme type based on index of enum's item
                    onThemeChanged(AppSettingsAppThemeType.entries[index])
                }
            )
        }
    }
}

@Composable
fun TTSSettingsSection(
    language: String,
    pitch: Float,
    speed: Float,
    onLanguageChanged: (String) -> Unit,
    onPitchChanged: (Float) -> Unit,
    onSpeedChanged: (Float) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        SettingGroupHeader(
            title = stringResource(R.string.app_settings_narration_section_header),
            subtitle = stringResource(R.string.app_settings_narration_section_body)
        )
        SettingItemWithTitle(
            title = stringResource(R.string.app_settings_narration_language_header)
        ) {
            // TODO: Get available narration languages (tags + names) from backend API
            val languageCodes = listOf("pl", "en")
            val languageLabels = listOf(
                stringResource(R.string.app_settings_narration_language_option_polish),
                stringResource(R.string.app_settings_narration_language_option_english)
            )

            val selectedIndex = languageCodes.indexOf(language).takeIf { it >= 0 } ?: 0

            PickerSetting(
                title = languageLabels[selectedIndex],
                promptTitle = stringResource(R.string.app_settings_narration_language_picker_header),

                options = languageLabels,
                selectedIndex = selectedIndex,
                onOptionSelected = { index ->
                    onLanguageChanged(languageCodes[index])
                },

                leadingIcon = {
                    Icon(
                        imageVector = Icons.Default.Language,
                        contentDescription = null
                    )
                }
            )
        }
        SettingItemWithTitle(
            title = stringResource(R.string.app_settings_narration_pitch_header)
        ) {
            Slider(value = pitch, onValueChange = onPitchChanged, valueRange = 0f..100f)
        }
        SettingItemWithTitle(
            title = stringResource(R.string.app_settings_narration_speed_header)
        ) {
            Slider(value = speed, onValueChange = onSpeedChanged, valueRange = 0f..10f)
        }
        Button(onClick = {}, modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.app_settings_narration_test_settings_button_content),
                style = MaterialTheme.typography.labelLarge
            )
        }
    }
}

@Composable
fun PlaybackSettingsSection(
    detailLevel: AppSettingsDetailLevelType,
    autoPlay: Boolean,
    onDetailLevelChanged: (AppSettingsDetailLevelType) -> Unit,
    onAutoPlayChanged: (Boolean) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        SettingGroupHeader(
            title = stringResource(R.string.app_settings_playback_section_header),
            subtitle = stringResource(R.string.app_settings_playback_section_body),
        )

        SettingItemWithTitle(
            title = stringResource(R.string.app_settings_playback_details_count_header)
        ) {
            val detailOptions = AppSettingsDetailLevelType.entries.map { level ->
                when (level) {
                    AppSettingsDetailLevelType.LOW -> stringResource(R.string.app_settings_playback_details_count_option_low)
                    AppSettingsDetailLevelType.MEDIUM -> stringResource(R.string.app_settings_playback_details_count_option_mid)
                    AppSettingsDetailLevelType.HIGH -> stringResource(R.string.app_settings_playback_details_count_option_high)
                }
            }

            SegmentedButton(
                options = detailOptions,
                selectedIndex = detailLevel.ordinal,
                onOptionSelected = { newIndex ->
                    onDetailLevelChanged(AppSettingsDetailLevelType.entries[newIndex])
                }
            )
        }

        SettingItemWithTitle(
            title = stringResource(R.string.app_settings_playback_interrupt_header)
        ) {
            val autoPlayValues = listOf(true, false)
            val autoPlayOptions = autoPlayValues.map { isAutoPlay ->
                if (isAutoPlay) {
                    stringResource(R.string.app_settings_playback_interrupt_option_yes)
                } else {
                    stringResource(R.string.app_settings_playback_interrupt_option_no)
                }
            }

            SegmentedButton(
                options = autoPlayOptions,
                selectedIndex = autoPlayValues.indexOf(autoPlay),
                onOptionSelected = { newIndex ->
                    onAutoPlayChanged(autoPlayValues[newIndex])
                }
            )
        }
    }
}

@Composable
fun AccountSettingsSection(modifier: Modifier = Modifier, backStack: NavBackStack<NavKey>? = null) {
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        SettingGroupHeader(
            title = stringResource(R.string.app_settings_account_section_header),
            subtitle = stringResource(R.string.app_settings_account_section_body)
        )
        Button(
            onClick = { backStack?.add(Route.AccountSettings) },
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(
                modifier = Modifier.padding(end = 8.dp),
                imageVector = Icons.Default.AccountCircle,
                contentDescription = null
            )
            Text(stringResource(R.string.app_settings_account_section_cta))
        }
    }
}
