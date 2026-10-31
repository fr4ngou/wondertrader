import { alertCategoryLabel, alertSourceLabel, alertTitle, alertValueLabel } from './problemDictionary'
import {
  formatAlertCategory, formatAlertSource, formatAlertTitle, formatAlertValue, formatOperationalAlert,
} from './operationalAlertFormat'
import type { OperationsSnapshot } from './types'

type OperationalAlert = NonNullable<OperationsSnapshot['alerts']>[number]
const labels = { category: alertCategoryLabel, source: alertSourceLabel, title: alertTitle, value: alertValueLabel }

export function operationalAlertCategoryLabel(category: string): string {
  return formatAlertCategory(labels, category)
}
export function operationalAlertSourceLabel(source: string): string {
  return formatAlertSource(labels, source)
}
export function operationalAlertTitle(alert: Pick<OperationalAlert, 'alert_key' | 'category'>): string {
  return formatAlertTitle(labels, alert)
}
export function operationalAlertValue(value: OperationalAlert['observed_value'], category: string): string {
  return formatAlertValue(labels, value, category)
}
export function operationalAlertPresentation(alert: OperationalAlert) {
  return formatOperationalAlert(labels, alert)
}
