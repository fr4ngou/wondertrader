import presentation from '../../config/market-observation-presentation.json'
import type { Catalog } from './types'

const hiddenBoards = new Set(['crossmarket', 'liquidity', 'swap', 'cffex', 'a50', 'northbound', 'institutions',
  'structure.csi2000', 'structure.star50', 'structure.ipo_supply'])
export const selectableBoard = (board: string) => board !== 'pending' && !hiddenBoards.has(board)

/** 统一排除已撤下看板的页面入口；原始目录与历史分区保持原归档。 */
export function selectableCatalog(catalog: Catalog): Catalog {
  return {
    ...catalog,
    boards: catalog.boards.filter(board => !hiddenBoards.has(board.id)),
    datasets: catalog.datasets.filter(item => !hiddenBoards.has(item.board)),
    recent_events: catalog.recent_events && Object.fromEntries(
      Object.entries(catalog.recent_events).filter(([board]) => !hiddenBoards.has(board))),
  }
}

export function defaultMetric(catalog:Catalog,board:string) {
  const defaults=presentation.default_datasets
  const constrained=(presentation.main_board_datasets as Record<string,string[]>)[board]
  const id=constrained ? defaults[board as keyof typeof defaults] : catalog.preferences.default_datasets[board] || defaults[board as keyof typeof defaults]
  return catalog.datasets.find(item=>item.id===id && item.board===board)?.id || catalog.datasets.find(item=>item.board===board)?.id
}

export function boardDatasets(catalog:Catalog) {
  const rules:Record<string,string[]> = presentation.main_board_datasets
  const labels:Record<string,string> = presentation.display_names
  return catalog.datasets.filter(item=>item.id!=='market.sh000001' && (!rules[item.board] || rules[item.board].includes(item.id))).map(item=>({...item,label:labels[item.id] || item.label}))
}
