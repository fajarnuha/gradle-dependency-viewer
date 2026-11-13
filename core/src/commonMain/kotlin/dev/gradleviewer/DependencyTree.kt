package dev.gradleviewer

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

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
        put("entries", entries)
        put("modules", modules.size)
        for ((field, pattern) in patterns) {
            val value = meta?.get(field) as? JsonPrimitive
            put(field, if (value != null && value.isString && pattern.matches(value.content)) value else JsonNull)
        }
    }
}
