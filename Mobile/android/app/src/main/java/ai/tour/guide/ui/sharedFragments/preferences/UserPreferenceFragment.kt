package ai.tour.guide.ui.sharedFragments.preferences

import ai.tour.guide.data.onboardingPreferences.OnboardingPreferenceQuestionDto
import ai.tour.guide.data.onboardingPreferences.OnboardingPreferenceQuestionType
import ai.tour.guide.ui.components.onboarding.LoadingOverlay
import ai.tour.guide.ui.components.shared.ToastOnRequestError
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.koin.compose.viewmodel.koinViewModel

@Composable
fun UserPreferenceFragment(
    modifier: Modifier = Modifier,
    viewModel: UserPreferenceFragmentViewModel = koinViewModel()
) {
    val preferences by viewModel.preferencesFlow.collectAsState()
    val viewState by viewModel.viewStateFlow.collectAsState()
    val lang = LocalConfiguration.current.locales[0].language

    LaunchedEffect(lang) {
        viewModel.onStart()
    }

    ToastOnRequestError(viewModel = viewModel)
    Column(
        modifier = modifier
            .padding(16.dp)
    ) {
        LazyColumn(Modifier.weight(1f)) {
            preferences.forEach { preference ->
                item(key = preference.key?.let { "header_$it" } ?: preference.hashCode()) {
                    Text(
                        text = preference.title ?: "",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )
                }

                val options = preference.options ?: emptyList()
                items(
                    items = options,
                    key = { item -> "${preference.key}_${item.key ?: item.hashCode()}" }
                ) { item ->
                    val isSingleChoice =
                        preference.type == OnboardingPreferenceQuestionType.SINGLE_CHOICE
                    val isSelected = if (isSingleChoice) {
                        viewState.data.selectedSingleOptions[preference.key] == item.key
                    } else {
                        viewState.data.selectedMultipleOptions[preference.key]?.contains(item.key) == true
                    }

                    PreferenceChoiceItem(
                        modifier = Modifier.testTag("preference_${preference.key}_${item.key}"),
                        item = item,
                        isSingleChoice = isSingleChoice,
                        isSelected = isSelected,
                        onSelect = {
                            if (preference.key != null && item.key != null) {
                                if (isSingleChoice) {
                                    viewModel.onOptionSelected(
                                        preference.key,
                                        item.key,
                                    )
                                } else {
                                    viewModel.onMultipleOptionToggled(
                                        preference.key,
                                        item.key,
                                    )
                                }
                            }
                        }
                    )
                }
            }
        }
        LoadingOverlay(isVisible = viewState.isLoading)
    }
}

@Composable
fun PreferenceChoiceItem(
    modifier: Modifier = Modifier,
    item: OnboardingPreferenceQuestionDto,
    isSingleChoice: Boolean,
    isSelected: Boolean,
    onSelect: () -> Unit
) {
    ListItem(
        modifier = modifier.clickable { onSelect() },
        leadingContent = {
            if (isSingleChoice) {
                RadioButton(selected = isSelected, onClick = null)
            } else {
                Checkbox(checked = isSelected, onCheckedChange = null)
            }
        },
        headlineContent = { Text(item.title ?: "") },
        supportingContent = { item.body?.let { Text(it) } },
        trailingContent = { item.trailingContent?.let { Text(it) } }
    )
}
