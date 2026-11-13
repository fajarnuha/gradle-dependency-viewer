package com.fajarnuha

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.fajarnuha.feature.featureDependencies
import com.fajarnuha.shared.SampleModules

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Scaffold { insets ->
                    Column(Modifier.padding(insets).padding(24.dp)) {
                        Text("Dependency Graph Sample", style = MaterialTheme.typography.headlineSmall)
                        Text(":app → :feature")
                        Text(":app → ${SampleModules.shared}")
                        Text(featureDependencies())
                    }
                }
            }
        }
    }
}
