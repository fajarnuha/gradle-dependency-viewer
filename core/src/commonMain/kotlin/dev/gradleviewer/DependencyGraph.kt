package dev.gradleviewer

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

fun toGraph(data: JsonObject, distance: Int? = null, exclude: String? = null): JsonObject {
    data.graphReportOrNull()?.let { return it.graph(distance, exclude) }
    val graphNodes = linkedMapOf<String, JsonObject>()
    val edges = linkedMapOf<String, MutableSet<String>>()
    val parents = mutableSetOf<String>()
    fun visit(items: List<JsonObject>, parent: String? = null) {
        for (node in items) {
            val id = node.id()
            graphNodes.getOrPut(id) {
                buildJsonObject {
                    put("id", id)
                    for (field in listOf("module", "version", "resolution", "full")) put(field, node.text(field))
                }
            }
            if (parent != null && parent.isNotEmpty()) {
                edges.getOrPut(parent) { linkedSetOf() }.add(id)
                parents.add(id)
            }
            visit(node.children(), id)
        }
    }
    val roots = nodes(rootKey(data)?.let { data[it] })
    visit(roots)
    if (roots.isNotEmpty()) {
        val root = "root:"
        graphNodes[root] = buildJsonObject {
            put("id", root)
            put("module", "root")
            put("version", "")
            put("resolution", "")
            put("full", "root")
        }
        val firstLevel = graphNodes.keys.filter { it != root && it !in parents }.toMutableList()
        val reachable = mutableSetOf<String>()
        fun markReachable(start: String) {
            val pending = mutableListOf(start)
            while (pending.isNotEmpty()) {
                val id = pending.removeAt(pending.lastIndex)
                if (reachable.add(id)) pending.addAll(edges[id].orEmpty())
            }
        }
        firstLevel.forEach(::markReachable)
        for (node in roots) {
            val id = node.id()
            if (id !in reachable) {
                firstLevel.add(id)
                markReachable(id)
            }
        }
        edges[root] = firstLevel.toMutableSet()
    }
    var included = graphNodes.keys.filter { exclude.isNullOrEmpty() || !it.contains(exclude) }.toSet()
    if (distance != null && "root:" in included) {
        var frontier = setOf("root:")
        val visited = frontier.toMutableSet()
        repeat(distance.coerceAtLeast(0).coerceAtMost(graphNodes.size)) {
            frontier = frontier.flatMap { edges[it].orEmpty() }.filter { it in included && it !in visited }.toSet()
            visited.addAll(frontier)
        }
        included = visited
    }
    val resultNodes = graphNodes.filterKeys { it in included }.values.toList()
    val resultEdges = edges.flatMap { (source, targets) ->
        targets.filter { source in included && it in included }.map { target ->
            buildJsonObject {
                put("source", source)
                put("target", target)
            }
        }
    }
    return graphView(resultNodes, resultEdges)
}

internal fun graphView(
    resultNodes: List<JsonElement>,
    resultEdges: List<JsonElement>,
    rootId: String? = null,
): JsonObject = buildJsonObject {
    if (rootId != null) put("rootId", rootId)
    put("nodes", JsonArray(resultNodes))
    put("edges", JsonArray(resultEdges))
    put("metadata", buildJsonObject {
        put("total_nodes", resultNodes.size)
        put("total_edges", resultEdges.size)
    })
}
