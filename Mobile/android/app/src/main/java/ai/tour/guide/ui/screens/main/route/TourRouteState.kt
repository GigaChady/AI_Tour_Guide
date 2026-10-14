package ai.tour.guide.ui.screens.main.route

import ai.tour.guide.network.schema.response.NarrationWordDto
import androidx.compose.ui.text.AnnotatedString

data class TourRouteState(
    val text: String,
    val styledText: AnnotatedString,
    val currentWordStartOffset: Int?,
    val words: List<NarrationWordDto>,
    val currentStopId: Int? = null,
    val currentStopIndex: Int? = null,
    val totalStops: Int? = null,
    val isSuccess: Boolean = false,
) {
    companion object {
        fun default() = TourRouteState(
            text = "",
            styledText = AnnotatedString(""),
            currentWordStartOffset = null,
            words = emptyList(),
            currentStopId = null,
            currentStopIndex = null,
            totalStops = null,
            isSuccess = false,
        )
    }
}
