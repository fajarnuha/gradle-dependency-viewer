package com.fajarnuha

import com.fajarnuha.feature.featureDependencies
import com.fajarnuha.shared.SampleModules
import org.junit.Assert.assertEquals
import org.junit.Test

class SampleDependenciesTest {
    @Test
    fun appAndFeatureReferToTheSameSharedModule() {
        assertEquals(SampleModules.shared, featureDependencies().substringAfter(" → "))
    }
}
