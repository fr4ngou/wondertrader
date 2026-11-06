/** 回测已知ETF简称；未匹配证券保留原WT代码，避免猜测名称。 */
const names: Record<string, string> = {
  '510500': '中证500ETF', '510050': '上证50ETF', '510300': '沪深300ETF', '512100': '中证1000ETF',
  '588000': '科创50ETF', '589680': '科创综指ETF',
  '515080': '红利ETF', '159780': '双创50ETF', '159352': 'A500ETF',
}
export const reportSymbol = (code: string) => {
  const number = code.match(/\d{6}/)?.[0]
  return number && names[number] ? `${names[number]} · ${number}` : code
}
