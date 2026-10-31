"""Pure versioned calculations; full history first, selected window afterwards."""
import math
from statistics import fmean, median, pstdev

def quantile(values, probability):
    values = sorted(v for v in values if v is not None)
    if not values: return None
    h = (len(values)-1)*probability; lo, hi = math.floor(h), math.ceil(h)
    return values[lo] + (values[hi]-values[lo])*(h-lo)

def derive(rows, definition, query, *, check=lambda: None):
    out = []; states = {}
    for original in rows:
        check()
        row = dict(original)
        if definition['board'] == 'pcr':
            row['call_count'] = row.get('call_'+query.pcr_type)
            row['put_count'] = row.get('put_'+query.pcr_type)
            call, put = row['call_count'], row['put_count']
            row = {key:value for key,value in row.items() if not key.startswith(('pcr_', 'reference_', 'official_'))}
            row['pcr'] = put/call if call and put is not None else None
        if definition.get('parameters'):
            inputs = (('', 'pcr'),) if definition['board'] == 'pcr' else (('', 'spread'),)
            for prefix, key in inputs:
                value = row.get(key)
                row.update({prefix+name: None for name in ('middle','upper','lower')})
                queue, ema, ema2 = states.get(prefix, ([], None, None))
                if value is None:
                    states[prefix] = ([], None, None)
                    continue
                alpha = 2/(query.window+1)
                ema = value if ema is None else alpha*value+(1-alpha)*ema
                ema2 = value*value if ema2 is None else alpha*value*value+(1-alpha)*ema2
                queue.append(value)
                if len(queue) > query.window: queue.pop(0)
                if len(queue) == query.window:
                    center = fmean(queue) if query.method == 'sma' else ema
                    sigma = math.sqrt(max(0, ema2-ema*ema)) if query.method == 'ema_moments' else pstdev(queue)
                    row.update({prefix+'middle': center, prefix+'upper': center+query.k*sigma, prefix+'lower': center-query.k*sigma})
                states[prefix] = (queue, ema, ema2)
        out.append(row)
    return out

def equal_pb(fields, rows, universe_codes):
    """Exactly the independent SH/SZ definition; preserve original strings elsewhere."""
    values = []; profitable = []; seen = set(); excluded = 0
    for data in rows:
        row = dict(zip(fields, data)); code = row['code']
        if code in seen: raise ValueError('duplicate stock/date')
        seen.add(code)
        if code not in universe_codes: continue
        pb = float(row['pbMRQ']) if row.get('pbMRQ') else None
        if row.get('tradestatus') == '1' and pb is not None and 0 < pb <= 100:
            values.append(pb)
            if row.get('peTTM') and float(row['peTTM']) > 0: profitable.append(pb)
        else: excluded += 1
    if not values: raise ValueError('no qualified PB observations')
    return dict(equal_pb=math.fsum(values)/len(values), median_pb=median(values),
                sample_count=len(values), excluded_count=excluded, universe_count=len(seen & universe_codes),
                profitable_equal_pb=math.fsum(profitable)/len(profitable) if profitable else None,
                profitable_median_pb=median(profitable) if profitable else None,
                profitable_sample_count=len(profitable), profitable_excluded_count=len(seen & universe_codes)-len(profitable))
