package com.fajarnuha.feature

import com.fajarnuha.shared.SampleModules

fun featureDependencies() = ":feature → ${SampleModules.shared}"
