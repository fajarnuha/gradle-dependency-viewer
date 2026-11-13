package dev.gradleviewer

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.put

@Serializable
data class GraphNode(
    val id: String,
    val module: String,
    val version: String,
    val resolution: String,
    val full: String,
)

@Serializable
data class GraphEdge(
    val source: String,
    val target: String,
    val requested: String,
    val constraint: Boolean,
)

@Serializable
data class DependencyGraphReport(
    val schemaVersion: Int,
    val projectPath: String,
    val configuration: String,
    val rootId: String,
    val nodes: List<GraphNode>,
    val edges: List<GraphEdge>,
) {
    init {
        require(schemaVersion == 1) { "Unsupported dependency graph schema version: $schemaVersion" }
        require(projectPath.isNotBlank() && configuration.isNotBlank()) {
            "Dependency graph must identify its project and configuration"
        }
        val ids = nodes.map { it.id }.toSet()
        require(ids.size == nodes.size && ids.none { it.isBlank() || '\u0000' in it }) {
            "Dependency graph node IDs must be unique and non-empty and cannot contain NUL"
        }
        require(rootId in ids) { "Dependency graph root '$rootId' does not exist" }
        require(edges.all { it.source in ids && it.target in ids }) {
            "Dependency graph edge refers to an unknown node"
        }
    }

    fun toJson(): JsonObject = dependencyJson.encodeToJsonElement(this) as JsonObject

    internal fun filtered(filter: String?, projectOnly: Boolean): DependencyGraphReport {
        val keywords = dependencyKeywords(filter)
        if (!projectOnly && keywords.isEmpty()) return this
        val outgoing = edges.groupBy { it.source }
        val included = if (projectOnly) {
            val projects = nodes.filter { isProjectModule(it.module) }.mapTo(mutableSetOf()) { it.id }
            reachable(listOf(rootId)) { source ->
                outgoing[source].orEmpty().map { it.target }.filter { it in projects }
            }
        } else {
            val matches = nodes.filter { it.id != rootId && matchesDependency(it.module, keywords) }.map { it.id }
            val incoming = edges.groupBy { it.target }
            reachable(matches) { target -> incoming[target].orEmpty().map { it.source } } +
                matches.flatMap { source -> outgoing[source].orEmpty().map { it.target } } + rootId
        }
        return retain(included)
    }

    internal fun graph(distance: Int?, exclude: String?): JsonObject {
        val eligible = nodes.filter { exclude.isNullOrEmpty() || !it.full.contains(exclude) }
            .mapTo(mutableSetOf()) { it.id }
        val outgoing = edges.groupBy { it.source }
        val included = if (distance != null && rootId in eligible) {
            val visited = mutableSetOf(rootId)
            var frontier = setOf(rootId)
            repeat(distance.coerceIn(0, nodes.size)) {
                frontier = frontier.flatMap { outgoing[it].orEmpty() }.mapNotNull {
                    it.target.takeIf { target -> target in eligible && visited.add(target) }
                }.toSet()
            }
            visited
        } else eligible
        val graphNodes = nodes.filter { it.id in included }.map { node ->
            val label = if (node.id == rootId) node.copy(module = "root") else node
            dependencyJson.encodeToJsonElement(label)
        }
        val graphEdges = edges.filter { it.source in included && it.target in included }
            .distinctBy { it.source to it.target }.map {
                buildJsonObject {
                    put("source", it.source)
                    put("target", it.target)
                }
            }
        return graphView(graphNodes, graphEdges, rootId.takeIf { it in included })
    }

    internal fun tree(): JsonObject {
        val byId = nodes.associateBy { it.id }
        val outgoing = edges.groupBy { it.source }
        val expanded = mutableSetOf(rootId)
        val roots = mutableListOf<JsonObject>()
        val pending = ArrayDeque<Pair<GraphEdge, MutableList<JsonObject>>>()
        outgoing[rootId].orEmpty().asReversed().forEach { pending.addLast(it to roots) }
        while (pending.isNotEmpty()) {
            val (edge, siblings) = pending.removeLast()
            val node = byId.getValue(edge.target)
            val repeated = !edge.constraint && !expanded.add(edge.target)
            val children = mutableListOf<JsonObject>()
            val full = if (edge.requested.isNotEmpty() && edge.requested != node.full) {
                "${edge.requested} -> ${node.version.ifEmpty { node.full }}"
            } else node.full
            siblings.add(buildJsonObject {
                put("module", node.module)
                put("version", node.version)
                put("resolution", when {
                    edge.constraint -> "c"
                    repeated -> "*"
                    else -> node.resolution
                })
                put("full", full)
                put("children", JsonArray(children))
            })
            if (!edge.constraint && !repeated) {
                outgoing[node.id].orEmpty().asReversed().forEach { pending.addLast(it to children) }
            }
        }
        return buildJsonObject { put(projectPath, JsonArray(roots)) }
    }

    internal fun coordinates(): List<String> = nodes.asSequence()
        .filter { it.id != rootId && it.version.isNotEmpty() && !isProjectModule(it.module) }
        .map { "${it.module}:${it.version}" }.distinct().sorted().toList()

    private fun retain(ids: Set<String>) = copy(
        nodes = nodes.filter { it.id in ids },
        edges = edges.filter { it.source in ids && it.target in ids },
    )
}

private fun reachable(start: List<String>, neighbors: (String) -> List<String>): Set<String> {
    val seen = start.toMutableSet()
    val pending = ArrayDeque(start)
    while (pending.isNotEmpty()) {
        for (next in neighbors(pending.removeFirst())) {
            if (seen.add(next)) pending.addLast(next)
        }
    }
    return seen
}

fun decodeDependencyGraph(data: JsonObject): DependencyGraphReport {
    val version = data["schemaVersion"] as? JsonPrimitive
    require(version != null && !version.isString && version.intOrNull != null) {
        "Expected a dependency graph with an integer schemaVersion"
    }
    return dependencyJson.decodeFromJsonElement(data)
}

internal fun JsonObject.graphReportOrNull(): DependencyGraphReport? =
    if (("schemaVersion" in this && get("schemaVersion") !is JsonArray) ||
        ("nodes" in this && "edges" in this && (rootKey(this) == null || "rootId" in this))
    ) {
        decodeDependencyGraph(this)
    } else null
