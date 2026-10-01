package dev.gradleviewer

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*

val dependencyJson = Json { encodeDefaults = true }
private val excludedKeys = setOf("raw_txt", "meta", "metadata", "nodes", "edges")

fun rootKey(data: JsonObject): String? = when {
    "root" in data -> "root"
    else -> data.entries.firstOrNull { it.key !in excludedKeys && it.value is JsonArray }?.key
}

private fun JsonObject.text(key: String): String {
    val value = get(key) ?: return ""
    require(value is JsonPrimitive && value.isString) { "$key must be a string" }
    return value.content
}

private fun nodes(value: JsonElement?): List<JsonObject> {
    if (value == null || value == JsonNull) return emptyList()
    require(value is JsonArray) { "Dependencies and children must be arrays" }
    return value.map {
        require(it is JsonObject) { "Dependency must be an object" }
        it
    }
}

private fun JsonObject.children() = nodes(get("children"))
private fun JsonObject.id() = text("module") + text("version").let { if (it.isEmpty()) "" else ":$it" }

@Serializable
private data class ParsedNode(
    val module: String,
    val version: String,
    val resolution: String,
    val full: String,
    val children: MutableList<ParsedNode> = mutableListOf(),
)

/** Gradle's tree markers use five columns per level. Repeated sections share one root list. */
fun parseDependencies(text: String): JsonObject {
    val lines = text.lineSequence().toList()
    val project = lines.firstNotNullOfOrNull {
        Regex("^Project ':([^']+)'").find(it.trim())?.groupValues?.get(1)
    } ?: "root"
    val roots = mutableListOf<ParsedNode>()
    val stack = mutableListOf<Pair<ParsedNode, Int>>()
    var parsing = false
    for (line in lines) {
        if (Regex("^\\w+(Runtime|Compile)Classpath").containsMatchIn(line)) {
            parsing = true
            continue
        }
        if (!parsing) continue
        val full = Regex("--- (.*)").find(line)?.groupValues?.get(1)?.trim() ?: continue
        val level = line.indexOfFirst { it !in " |\\+-" }.let { if (it < 0) 0 else it / 5 }
        val parts = full.substringBefore(" -> ").split(':')
        val isProject = full.startsWith("project ")
        val module = when {
            isProject -> full.replace(Regex("\\s*\\(\\*\\)\\s*$"), "")
            parts.size > 2 -> parts.take(2).joinToString(":")
            " -> " in full -> full.substringBefore(" -> ")
            else -> full
        }
        val versionPart = when {
            isProject -> ""
            " -> " in full -> full.substringAfter(" -> ").substringBefore(" -> ")
            parts.size > 2 -> parts[2]
            else -> ""
        }
        val version = Regex("[\\d.\\-a-zA-Z]+").find(versionPart)?.value.orEmpty()
        val resolution = Regex("\\(([*+c])\\)").find(full)?.groupValues?.get(1).orEmpty()
        val node = ParsedNode(module, version, resolution, full)
        while (stack.isNotEmpty() && stack.last().second >= level) stack.removeAt(stack.lastIndex)
        if (stack.isEmpty()) roots.add(node) else stack.last().first.children.add(node)
        stack.add(node to level)
    }
    return buildJsonObject { put(project, dependencyJson.encodeToJsonElement(roots)) }
}

fun filterDependencies(data: JsonObject, filter: String? = null, projectOnly: Boolean = false): JsonObject {
    val key = rootKey(data) ?: return data
    val roots = nodes(data[key])
    val keywords = filter.orEmpty().split(',').map { it.trim() }.filter { it.isNotEmpty() }
    if (!projectOnly && keywords.isEmpty()) return data
    val kept = mutableSetOf<String>()
    fun findMatches(items: List<JsonObject>, ancestors: List<JsonObject>) {
        for (node in items) {
            val path = ancestors + node
            if (keywords.any { node.text("module").contains(it, ignoreCase = true) }) {
                (path + node.children()).forEach { kept.add(it.text("full")) }
            }
            findMatches(node.children(), path)
        }
    }
    if (!projectOnly && keywords.isNotEmpty()) findMatches(roots, emptyList())
    fun rebuild(items: List<JsonObject>): JsonArray = JsonArray(items.mapNotNull { node ->
        val keep = when {
            projectOnly -> node.text("module").startsWith("project ")
            keywords.isNotEmpty() -> node.text("full") in kept
            else -> true
        }
        if (keep) JsonObject(node + ("children" to rebuild(node.children()))) else null
    })
    return JsonObject(data + (key to rebuild(roots)))
}

fun treeView(data: JsonObject): JsonObject = JsonObject(data - setOf("raw_txt", "meta"))

fun toGraph(data: JsonObject, distance: Int? = null, exclude: String? = null): JsonObject {
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
            put("id", root); put("module", "root"); put("version", ""); put("resolution", ""); put("full", "root")
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
            if (id !in reachable) { firstLevel.add(id); markReachable(id) }
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
            buildJsonObject { put("source", source); put("target", target) }
        }
    }
    return buildJsonObject {
        put("nodes", JsonArray(resultNodes))
        put("edges", JsonArray(resultEdges))
        put("metadata", buildJsonObject { put("total_nodes", resultNodes.size); put("total_edges", resultEdges.size) })
    }
}

fun enlistDependencies(data: JsonObject): List<String> {
    val dependencies = mutableSetOf<String>()
    fun visit(items: List<JsonObject>) {
        for (node in items) {
            if (node.text("version").isNotEmpty()) dependencies.add(node.id())
            visit(node.children())
        }
    }
    visit(nodes(rootKey(data)?.let { data[it] }))
    return dependencies.sorted()
}

fun enlistYaml(data: JsonObject): String {
    val dependencies = enlistDependencies(data)
    // JSON-quoted strings are valid YAML scalars; this fixed document needs no YAML library.
    return if (dependencies.isEmpty()) "dependencies: []\ntotal_count: 0\n" else
        "dependencies:\n" + dependencies.joinToString("") { "- ${JsonPrimitive(it)}\n" } + "total_count: ${dependencies.size}\n"
}

fun sampleSummary(data: JsonObject): JsonObject {
    var entries = 0
    val modules = mutableSetOf<String>()
    val stack = nodes(rootKey(data)?.let { data[it] }).toMutableList()
    while (stack.isNotEmpty()) {
        val node = stack.removeAt(stack.lastIndex)
        entries++
        modules.add(node.text("module"))
        stack.addAll(node.children())
    }
    val meta = data["meta"] as? JsonObject
    val patterns = mapOf(
        "repository" to Regex("https://github\\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+"),
        "commit" to Regex("[0-9a-f]{40}"),
        "icon" to Regex("data:image/(?:png|webp);base64,[A-Za-z0-9+/]+=*"),
    )
    return buildJsonObject {
        put("entries", entries); put("modules", modules.size)
        for ((field, pattern) in patterns) {
            val value = meta?.get(field) as? JsonPrimitive
            put(field, if (value != null && value.isString && pattern.matches(value.content)) value else JsonNull)
        }
    }
}
