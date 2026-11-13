package dev.gradleviewer

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class DependencyGraphReportTest {
    private val report = DependencyGraphReport(
        schemaVersion = 1,
        projectPath = ":app",
        configuration = "debugRuntimeClasspath",
        rootId = "root",
        nodes = listOf(
            GraphNode("root", "project :app", "", "", "project :app"),
            GraphNode("feature", "project :feature", "", "", "project :feature"),
            GraphNode("shared", "project :shared", "", "", "project :shared"),
            GraphNode("external", "org.example:widget", "2", "", "org.example:widget:2"),
            GraphNode("runtime", "org.example:widget", "2", "", "org.example:widget:2"),
            GraphNode("nested", "org.example:nested", "1", "", "org.example:nested:1"),
        ),
        edges = listOf(
            GraphEdge("root", "feature", "project :feature", false),
            GraphEdge("root", "shared", "project :shared", false),
            GraphEdge("feature", "shared", "project :shared", false),
            GraphEdge("feature", "external", "org.example:widget:1", false),
            GraphEdge("shared", "feature", "project :feature", false),
            GraphEdge("shared", "runtime", "org.example:widget:2", true),
            GraphEdge("shared", "runtime", "org.example:widget:2", false),
            GraphEdge("runtime", "nested", "org.example:nested:1", false),
        ),
    )

    @Test
    fun graphPreservesDirectEdgesAndTreeStopsCycles() {
        val data = report.toJson()
        assertEquals(report, decodeDependencyGraph(data))
        val graph = toGraph(data)
        assertEquals("root", graph.text("rootId"))
        assertTrue(graph.getValue("edges").jsonArray.any {
            it.jsonObject.text("source") == "root" && it.jsonObject.text("target") == "shared"
        })
        val roots = treeView(data).getValue(":app").jsonArray.map { it.jsonObject }
        val shared = roots.first().children().first()
        assertEquals("*", shared.children().first().text("resolution"))
        assertTrue(shared.children().first().children().isEmpty())
        assertEquals("c", shared.children()[1].text("resolution"))
        assertTrue(shared.children()[1].children().isEmpty())
        assertEquals("org.example:nested", shared.children()[2].children().single().text("module"))
        assertEquals("*", roots.last().text("resolution"))
        assertEquals("org.example:widget:1 -> 2", roots.first().children()[1].text("full"))
    }

    @Test
    fun filtersAndExportsSelectedCoordinates() {
        val projects = decodeDependencyGraph(filterDependencies(report.toJson(), projectOnly = true))
        assertEquals(setOf("root", "shared", "feature"), projects.nodes.map { it.id }.toSet())
        val filtered = decodeDependencyGraph(filterDependencies(report.toJson(), "WIDGET"))
        assertEquals(report.nodes, filtered.nodes)
        val feature = decodeDependencyGraph(filterDependencies(report.toJson(), ":feature"))
        assertEquals(setOf("root", "feature", "shared", "external"), feature.nodes.map { it.id }.toSet())
        val excluded = toGraph(report.toJson(), distance = 1, exclude = "shared")
        assertEquals(listOf("root", "feature"), excluded.getValue("nodes").jsonArray.map { it.jsonObject.text("id") })
        val noMatches = decodeDependencyGraph(filterDependencies(report.toJson(), "absent"))
        assertEquals(listOf("root"), noMatches.nodes.map { it.id })
        assertEquals(listOf("org.example:nested:1", "org.example:widget:2"), enlistDependencies(report.toJson()))
    }

    @Test
    fun validatesReferencesAndSupportsEmptyGraphs() {
        assertFailsWith<IllegalArgumentException> { report.copy(schemaVersion = 2) }
        assertFailsWith<IllegalArgumentException> { report.copy(rootId = "missing") }
        assertFailsWith<IllegalArgumentException> { report.copy(nodes = report.nodes + report.nodes.first()) }
        assertFailsWith<IllegalArgumentException> {
            report.copy(edges = report.edges + GraphEdge("root", "missing", "", false))
        }
        val empty = report.copy(nodes = listOf(report.nodes.first()), edges = emptyList()).toJson()
        assertEquals(1, toGraph(empty).getValue("nodes").jsonArray.size)
        assertEquals(JsonArray(emptyList()), treeView(empty).getValue(":app"))
        assertEquals("0", toGraph(empty).getValue("metadata").jsonObject.getValue("total_edges").jsonPrimitive.content)
    }
}
