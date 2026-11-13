package com.fajarnuha.dependency_graph

import dev.gradleviewer.DependencyGraphReport
import dev.gradleviewer.decodeDependencyGraph
import dev.gradleviewer.dependencyJson
import kotlinx.serialization.json.jsonObject
import org.gradle.testkit.runner.GradleRunner
import org.junit.Rule
import org.junit.rules.TemporaryFolder
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DependencyGraphPluginTest {
    @get:Rule val fixture = TemporaryFolder()

    @Test
    fun exportsSelectedDependenciesAndReusesConfigurationCache() {
        write("settings.gradle", "rootProject.name = 'fixture'\ninclude 'feature', 'shared'")
        write("build.gradle", """
            plugins {
                id 'java'
                id 'com.fajarnuha.dependency-graph'
            }
            allprojects {
                repositories { maven { url = rootProject.file('repo') } }
            }
            dependencies {
                implementation project(':feature')
                implementation project(':shared')
                implementation 'org.example:widget:1.0'
            }
        """.trimIndent())
        write("feature/build.gradle", """
            plugins { id 'java-library' }
            dependencies {
                implementation project(':shared')
                implementation 'org.example:widget:2.0'
                constraints { implementation 'org.example:widget:2.0' }
            }
        """.trimIndent())
        write("shared/build.gradle", "plugins { id 'java-library' }")
        for (version in listOf("1.0", "2.0")) {
            write("repo/org/example/widget/$version/widget-$version.pom", """
                <project>
                  <modelVersion>4.0.0</modelVersion>
                  <groupId>org.example</groupId>
                  <artifactId>widget</artifactId>
                  <version>$version</version>
                </project>
            """.trimIndent())
        }

        runner("exportDependencyGraph", "--configuration-cache").build()
        val reportFile = reportFile()
        val first = reportFile.readText()
        val graph = readReport(reportFile)
        val feature = graph.nodes.single { it.module == "project :feature" }
        val shared = graph.nodes.single { it.module == "project :shared" }
        val widget = graph.nodes.single { it.module == "org.example:widget" }
        assertEquals("2.0", widget.version)
        assertTrue(graph.edges.any { it.source == graph.rootId && it.target == shared.id })
        assertTrue(graph.edges.any { it.source == feature.id && it.target == shared.id })
        assertTrue(graph.edges.any { it.target == widget.id && it.requested == "org.example:widget:1.0" })
        assertTrue(graph.edges.any { it.target == widget.id && it.constraint })
        val second = runner("exportDependencyGraph", "--configuration-cache").build()
        assertTrue(second.output.contains("Reusing configuration cache."))
        assertEquals(first, reportFile.readText())
        assertFalse(File(fixture.root, "build/libs").exists())
    }

    @Test
    fun reportsInvalidConfigurationsAndPreservesLastSuccessfulExport() {
        write("settings.gradle", "rootProject.name = 'fixture'")
        val build = """
            plugins {
                id 'java'
                id 'com.fajarnuha.dependency-graph'
            }
            repositories { maven { url = file('repo') } }
        """.trimIndent()
        write("build.gradle", build)
        val tasks = runner("tasks", "--all", "-PdependencyGraphConfiguration=missing").build()
        assertTrue(tasks.output.contains("exportDependencyGraph"))
        runner("exportDependencyGraph").build()
        val reportFile = reportFile()
        val empty = reportFile.readText()
        assertEquals(1, readReport(reportFile).nodes.size)
        assertTrue(readReport(reportFile).edges.isEmpty())
        for ((name, detail) in mapOf("missing" to "does not exist", "implementation" to "cannot be resolved")) {
            val result = runner("exportDependencyGraph", "-PdependencyGraphConfiguration=$name").buildAndFail()
            assertTrue(result.output.contains("Configuration '$name'"))
            assertTrue(result.output.contains(detail))
        }
        write("build.gradle", "$build\ndependencies { implementation 'org.example:missing:1.0' }")
        val failed = runner("exportDependencyGraph").buildAndFail()
        assertTrue(failed.output.contains("Could not resolve org.example:missing:1.0"), failed.output)
        assertEquals(empty, reportFile.readText())
    }

    private fun runner(vararg args: String): GradleRunner = GradleRunner.create()
        .withProjectDir(fixture.root)
        .withPluginClasspath()
        .withArguments(args.toList() + "--offline")

    private fun write(path: String, contents: String) {
        val file = File(fixture.root, path)
        file.parentFile.mkdirs()
        file.writeText(contents)
    }

    private fun reportFile() = File(fixture.root, "build/reports/dependency-graph/runtimeClasspath.json")

    private fun readReport(file: File): DependencyGraphReport =
        decodeDependencyGraph(dependencyJson.parseToJsonElement(file.readText()).jsonObject)
}
