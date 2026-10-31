import type { ProblemDefinition, ProblemDictionary } from './types'

let currentDictionary: ProblemDictionary = {
  schema_version: '1.0',
  definitions: [],
  alert_category_labels: {},
  alert_source_labels: {},
  alert_titles: {},
  alert_value_labels: {},
}
let definitionsByValue = new Map<string, ProblemDefinition>()

export function installProblemDictionary(dictionary: ProblemDictionary): ProblemDictionary {
  if (!dictionary || !Array.isArray(dictionary.definitions)) return currentDictionary
  currentDictionary = {
    ...dictionary,
    alert_category_labels: dictionary.alert_category_labels ?? {},
    alert_source_labels: dictionary.alert_source_labels ?? {},
    alert_titles: dictionary.alert_titles ?? {},
    alert_value_labels: dictionary.alert_value_labels ?? {},
  }
  definitionsByValue = new Map()
  currentDictionary.definitions.forEach((definition) => {
    definitionsByValue.set(definition.issue_code, definition)
    ;(definition.match_values ?? []).forEach((value) => definitionsByValue.set(value, definition))
  })
  return dictionary
}

export function problemDefinitionFor(value: string): ProblemDefinition | undefined {
  return definitionsByValue.get(value)
}

export function problemDefinitions(): ProblemDefinition[] {
  return currentDictionary.definitions
}

export function alertCategoryLabel(category: string): string | undefined {
  return currentDictionary.alert_category_labels?.[category]
}

export function alertSourceLabel(source: string): string | undefined {
  return currentDictionary.alert_source_labels?.[source]
}

export function alertTitle(key: string): string | undefined {
  return currentDictionary.alert_titles?.[key]
}

export function alertValueLabel(value: string): string | undefined {
  return currentDictionary.alert_value_labels?.[value]
}
