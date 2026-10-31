import presentation from '../../config/market-observation-presentation.json'
import type { Catalog } from './types'

export function defaultMetric(catalog:Catalog,board:string) {
  const defaults=presentation.default_datasets
  const constrained=(presentation.main_board_datasets as Record<string,string[]>)[board]
  const id=constrained ? defaults[board as keyof typeof defaults] : catalog.preferences.default_datasets[board] || defaults[board as keyof typeof defaults]
  return catalog.datasets.find(item=>item.id===id && item.board===board)?.id || catalog.datasets.find(item=>item.board===board)?.id
}

export function boardDatasets(catalog:Catalog) {
  const rules:Record<string,string[]> = presentation.main_board_datasets
  const labels:Record<string,string> = presentation.display_names
  return catalog.datasets.filter(item=>!rules[item.board] || rules[item.board].includes(item.id)).map(item=>({...item,label:labels[item.id] || item.label}))
}
