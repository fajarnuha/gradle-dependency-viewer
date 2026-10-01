package dev.gradleviewer

import kotlinx.serialization.json.*
import kotlin.test.*

class DependenciesTest {
    private val report = """
        Project ':app'
        debugRuntimeClasspath - dependencies
        +--- project :feature (*)
        |    +--- org.example:a:1.0 -> 2.0 (c)
        |    |    \--- org.example:b:3.0
        |    \--- project :shared
        \--- org.example:a:2.0 (*)
    """.trimIndent()

    @Test fun parserFiltersGraphAndEnlist() {
        val data = parseDependencies(report)
        assertEquals("app", rootKey(data))
        val roots = data.getValue("app").jsonArray
        assertEquals(2, roots.size)
        val feature = roots[0].jsonObject
        assertEquals("project :feature", feature["module"]?.jsonPrimitive?.content)
        val a = feature.getValue("children").jsonArray[0].jsonObject
        assertEquals("2.0", a["version"]?.jsonPrimitive?.content)
        assertEquals("c", a["resolution"]?.jsonPrimitive?.content)
        assertEquals(listOf("org.example:a:2.0", "org.example:b:3.0"), enlistDependencies(data))
        assertEquals("dependencies:\n- \"org.example:a:2.0\"\n- \"org.example:b:3.0\"\ntotal_count: 2\n", enlistYaml(data))

        val projects = filterDependencies(data, "org.example", projectOnly = true)["app"]!!.jsonArray
        assertEquals(1, projects.size)
        assertEquals("project :shared", projects[0].jsonObject.getValue("children").jsonArray[0].jsonObject["module"]!!.jsonPrimitive.content)
        val filtered = filterDependencies(data, "B, no-match")
        assertEquals(listOf("org.example:a:2.0", "org.example:b:3.0"), enlistDependencies(filtered))
        assertEquals(0, filterDependencies(data, "missing")["app"]!!.jsonArray.size)
        assertEquals(JsonArray(emptyList()), toGraph(filterDependencies(data, "missing"))["nodes"])

        val graph = toGraph(data)
        assertEquals(5, graph["metadata"]!!.jsonObject["total_nodes"]!!.jsonPrimitive.int)
        assertEquals(4, graph["metadata"]!!.jsonObject["total_edges"]!!.jsonPrimitive.int)
        assertEquals(1, toGraph(data, distance = 0)["nodes"]!!.jsonArray.size)
        assertEquals(2, toGraph(data, distance = 1)["nodes"]!!.jsonArray.size)
        assertFalse(toGraph(data, exclude = "org.example")["nodes"]!!.jsonArray.any { it.jsonObject["id"]!!.jsonPrimitive.content.startsWith("org.example") })
        assertEquals(data, parseDependencies(report.replace("\n", "\r\n")))
        assertEquals("root", rootKey(parseDependencies("No dependencies")))
    }

    @Test fun cyclesRemainReachableAndNodesAreDeduplicated() {
        val cycle = parseDependencies("debugRuntimeClasspath\n+--- a:a:1\n|    \\--- b:b:1\n|         \\--- a:a:1 (*)")
        val graph = toGraph(cycle)
        assertEquals(3, graph["nodes"]!!.jsonArray.size)
        assertEquals(3, graph["edges"]!!.jsonArray.size)
        assertEquals(3, toGraph(cycle, distance = 2)["nodes"]!!.jsonArray.size)
        assertTrue(graph["edges"]!!.jsonArray.any { it.jsonObject["source"]!!.jsonPrimitive.content == "root:" })
    }

    @Test fun metadataAndInvalidData() {
        val data = parseDependencies(report)
        val withMeta = JsonObject(data + mapOf("meta" to buildJsonObject {
            put("repository", "javascript:alert(1)"); put("commit", "main"); put("icon", "data:image/svg+xml;base64,AAAA")
        }, "raw_txt" to JsonPrimitive(report)))
        assertEquals(data, treeView(withMeta))
        assertEquals(JsonNull, sampleSummary(withMeta)["repository"])
        assertEquals(JsonNull, sampleSummary(withMeta)["icon"])
        assertEquals(5, sampleSummary(data)["entries"]!!.jsonPrimitive.int)
        assertEquals(4, sampleSummary(data)["modules"]!!.jsonPrimitive.int)
        assertEquals(2, withMeta.size - data.size)
        assertFailsWith<IllegalArgumentException> { toGraph(buildJsonObject { put("root", "bad") }) }
        assertFailsWith<IllegalArgumentException> { toGraph(buildJsonObject { put("root", JsonArray(listOf(JsonPrimitive(1)))) }) }
    }
}
