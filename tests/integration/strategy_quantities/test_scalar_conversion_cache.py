"""读取侧纯标量复用的原解析等价、错误隔离、容量与并发回归。"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, Inexact, InvalidOperation, Rounded, localcontext
from fractions import Fraction
import random
from types import SimpleNamespace
import unittest

from guanheng_strategy_native import _numbers as current

original = SimpleNamespace(number=current._number, rational=current._rational)


def outcome(operation, *values, **options):
    try:
        value = operation(*values, **options)
        return ('value', value.numerator, value.denominator) if type(value) is Fraction else ('value', type(value).__name__, value)
    except Exception as error:
        return ('error', type(error).__name__, str(error))


class ScalarConversionCacheTests(unittest.TestCase):
    def setUp(self):
        current._cached_number.cache_clear()
        current._cached_rational.cache_clear()

    def test_exact_values_types_errors_and_decimal_contexts(self):
        class Text(str): pass
        class Integer(int): pass
        values=[None,True,False,[],{},Text('1'),Integer(1),0,-1,2**256-1,2**256,
            Decimal('1.500'),Decimal('NaN'),Decimal('sNaN'),Decimal('Infinity'),Decimal('-0'),
            '', ' ', '0','-0','1.000','-1.25','1e64','1e65','1e-64','1e-65','1e999999',
            '+1','.1','01','NaN','Infinity','1\n','１','中', '1'*65,'x'*257]
        rng=random.Random(20261031)
        values.extend(str(rng.randrange(-10**12,10**12)/1000) for _ in range(1500))
        for restricted in (False,True):
            with localcontext() as context:
                if restricted:
                    context.prec=2;context.Emin=-2;context.Emax=2
                    for signal in (Inexact,Rounded,InvalidOperation):context.traps[signal]=True
                for value in values:
                    for signed in (False,True):
                        expected=outcome(original.number,value,'synthetic.amount',signed=signed)
                        self.assertEqual(outcome(current.number,value,'synthetic.amount',signed=signed),expected)
                        self.assertEqual(outcome(current.number,value,'synthetic.amount',signed=signed),expected)
                    # 避免诊断用极大指数构造巨大整数；它仍按原number路径拒绝。
                    if value!='1e999999':
                        expected=outcome(original.rational,value)
                        self.assertEqual(outcome(current.rational,value),expected)
                        self.assertEqual(outcome(current.rational,value),expected)

    def test_failed_values_and_opaque_parameters_are_not_retained(self):
        for name in ('first','second','x'*257,[]):
            for value in ('invalid',-1,True):
                self.assertEqual(outcome(current.number,value,name),outcome(original.number,value,name))
        for signed in (None,0,1,[],[1]):
            self.assertEqual(outcome(current.number,'-1','amount',signed=signed),
                             outcome(original.number,'-1','amount',signed=signed))
        caught=[]
        for _ in range(2):
            try:current.number('invalid','amount')
            except current.QuantityError as error:caught.append(error)
        self.assertEqual(len(caught),2)
        self.assertIsNot(caught[0],caught[1])

    def test_fraction_private_mutation_cannot_poison_later_results(self):
        first=current.rational('1.25');second=current.rational('1.25')
        self.assertIsNot(first,second)
        first._numerator=999
        second._denominator=7
        self.assertEqual(current.rational('1.25'),Fraction(5,4))

    def test_success_caches_are_bounded_and_evict_without_changing_values(self):
        for index in range(3000):
            self.assertEqual(current.number(str(index),'amount'),str(index))
            self.assertEqual(current.rational(str(index)),Fraction(index))
        for cached in (current._cached_number,current._cached_rational):
            self.assertEqual(cached.cache_info().maxsize,2048)
            self.assertLessEqual(cached.cache_info().currsize,2048)
        self.assertEqual(current.number('0','amount'),'0')
        self.assertEqual(current.rational('0'),Fraction(0))

    def test_shared_cache_concurrent_callers_receive_independent_exact_values(self):
        def consume(index):
            for _ in range(300):
                self.assertEqual(current.number('1.2500','amount'),'1.25')
                value=current.rational('1.25')
                self.assertEqual(value,Fraction(5,4))
                value._numerator=index
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(consume,range(4)))
        self.assertEqual(current.rational('1.25'),Fraction(5,4))
