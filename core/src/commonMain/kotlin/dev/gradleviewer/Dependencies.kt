package dev.gradleviewer

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

val dependencyJson = Json { encodeDefaults = true }
private val excludedKeys = setOf("raw_txt", "meta", "metadata", "nodes", "edges")

fun rootKey(data: JsonObject): String? = when {
    "root" in data -> "root"
    else -> data.entries.firstOrNull { it.key !in excludedKeys && it.value is JsonArray }?.key
}

internal fun JsonObject.text(key: String): String {
    val value = get(key) ?: return ""
    require(value is JsonPrimitive && value.isString) { "$key must be a string" }
    return value.content
}

internal fun nodes(value: JsonElement?): List<JsonObject> {
    if (value == null || value == JsonNull) return emptyList()
    require(value is JsonArray) { "Dependencies and children must be arrays" }
    return value.map {
        require(it is JsonObject) { "Dependency must be an object" }
        it
    }
}

internal fun JsonObject.children() = nodes(get("children"))
internal fun JsonObject.id() = text("module") + text("version").let { if (it.isEmpty()) "" else ":$it" }

internal fun dependencyKeywords(filter: String?) =
    filter.orEmpty().split(',').map { it.trim() }.filter { it.isNotEmpty() }

internal fun matchesDependency(module: String, keywords: List<String>) =
    keywords.any { module.contains(it, ignoreCase = true) }

internal fun isProjectModule(module: String) = module.startsWith("project ")
