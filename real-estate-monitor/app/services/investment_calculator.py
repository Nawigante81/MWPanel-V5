"""
Investment Calculator Service

Professional-grade investment analysis tools for real estate investors.
Calculates ROI, cash flow, cap rate, and other key metrics.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json

from app.core.logging import get_logger

logger = get_logger(__name__)


class InvestmentStrategy(str, Enum):
    """Real estate investment strategies"""
    BUY_AND_HOLD = "buy_and_hold"
    FIX_AND_FLIP = "fix_and_flip"
    BRRRR = "brrrr"  # Buy, Rehab, Rent, Refinance, Repeat
    SHORT_TERM_RENTAL = "short_term_rental"
    COMMERCIAL = "commercial"
    LAND_DEVELOPMENT = "land_development"


class FinancingType(str, Enum):
    """Types of financing"""
    CASH = "cash"
    CONVENTIONAL_MORTGAGE = "conventional_mortgage"
    FHA = "fha"
    VA = "va"
    HARD_MONEY = "hard_money"
    PRIVATE_LENDER = "private_lender"
    SELLER_FINANCING = "seller_financing"
    COMMERCIAL_LOAN = "commercial_loan"


@dataclass
class PurchaseDetails:
    """Property purchase details"""
    purchase_price: float
    closing_costs: float = 0.0
    renovation_costs: float = 0.0
    furniture_costs: float = 0.0  # For furnished rentals
    other_costs: float = 0.0
    
    @property
    def total_investment(self) -> float:
        return (
            self.purchase_price +
            self.closing_costs +
            self.renovation_costs +
            self.furniture_costs +
            self.other_costs
        )


@dataclass
class FinancingDetails:
    """Loan/financing details"""
    financing_type: FinancingType = FinancingType.CASH
    down_payment_percent: float = 25.0  # Default 25% for investment
    loan_amount: float = 0.0
    interest_rate: float = 6.5  # Annual percentage
    loan_term_years: int = 30
    points_upfront: float = 0.0  # Loan origination points
    other_loan_costs: float = 0.0
    
    def calculate_down_payment(self, purchase_price: float) -> float:
        """Calculate down payment amount"""
        if self.financing_type == FinancingType.CASH:
            return purchase_price
        return purchase_price * (self.down_payment_percent / 100)
    
    def calculate_monthly_payment(self) -> float:
        """Calculate monthly mortgage payment"""
        if self.financing_type == FinancingType.CASH or self.loan_amount <= 0:
            return 0.0
        
        monthly_rate = self.interest_rate / 100 / 12
        num_payments = self.loan_term_years * 12
        
        if monthly_rate == 0:
            return self.loan_amount / num_payments
        
        payment = (
            self.loan_amount *
            (monthly_rate * (1 + monthly_rate) ** num_payments) /
            ((1 + monthly_rate) ** num_payments - 1)
        )
        return payment


@dataclass
class IncomeProjections:
    """Rental income projections"""
    monthly_rent: float
    vacancy_rate: float = 5.0  # Percentage
    other_monthly_income: float = 0.0  # Parking, laundry, etc.
    annual_rent_increase: float = 3.0  # Percentage
    
    @property
    def effective_gross_income(self) -> float:
        """Annual income accounting for vacancy"""
        annual_rent = self.monthly_rent * 12
        vacancy_loss = annual_rent * (self.vacancy_rate / 100)
        other_income = self.other_monthly_income * 12
        return annual_rent - vacancy_loss + other_income


@dataclass
class OperatingExpenses:
    """Property operating expenses"""
    property_tax_annual: float = 0.0
    insurance_annual: float = 0.0
    property_management_percent: float = 10.0
    maintenance_percent: float = 5.0
    capex_reserve_percent: float = 5.0  # Capital expenditures reserve
    utilities_monthly: float = 0.0  # If owner pays
    hoa_fees_monthly: float = 0.0
    other_expenses_monthly: float = 0.0
    
    def calculate_total_annual(
        self,
        effective_gross_income: float,
        monthly_rent: float
    ) -> float:
        """Calculate total annual operating expenses"""
        property_management = effective_gross_income * (self.property_management_percent / 100)
        maintenance = effective_gross_income * (self.maintenance_percent / 100)
        capex_reserve = effective_gross_income * (self.capex_reserve_percent / 100)
        
        utilities = self.utilities_monthly * 12
        hoa = self.hoa_fees_monthly * 12
        other = self.other_expenses_monthly * 12
        
        return (
            self.property_tax_annual +
            self.insurance_annual +
            property_management +
            maintenance +
            capex_reserve +
            utilities +
            hoa +
            other
        )


@dataclass
class InvestmentMetrics:
    """Calculated investment metrics"""
    # Cash flow
    monthly_cash_flow: float = 0.0
    annual_cash_flow: float = 0.0
    
    # Returns
    cash_on_cash_return: float = 0.0  # Percentage
    cap_rate: float = 0.0  # Percentage
    total_roi_annual: float = 0.0  # Percentage
    
    # Ratios
    gross_rent_multiplier: float = 0.0
    debt_service_coverage_ratio: float = 0.0
    price_to_rent_ratio: float = 0.0
    
    # Break-even
    break_even_occupancy: float = 0.0  # Percentage
    break_even_rent: float = 0.0
    
    # 50% Rule check
    fifty_percent_rule_estimate: float = 0.0
    fifty_percent_rule_pass: bool = False
    
    # 1% / 2% Rule
    one_percent_rule_pass: bool = False
    two_percent_rule_pass: bool = False
    
    # 5-year projection
    five_year_roi: float = 0.0
    five_year_cash_flow: float = 0.0
    five_year_appreciation: float = 0.0
    
    # Detailed breakdown
    noi_annual: float = 0.0  # Net Operating Income
    effective_gross_income: float = 0.0
    operating_expenses_annual: float = 0.0
    mortgage_payment_annual: float = 0.0
    total_cash_invested: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'cash_flow': {
                'monthly': round(self.monthly_cash_flow, 2),
                'annual': round(self.annual_cash_flow, 2),
            },
            'returns': {
                'cash_on_cash_return': round(self.cash_on_cash_return, 2),
                'cap_rate': round(self.cap_rate, 2),
                'total_roi_annual': round(self.total_roi_annual, 2),
            },
            'ratios': {
                'gross_rent_multiplier': round(self.gross_rent_multiplier, 2),
                'debt_service_coverage_ratio': round(self.debt_service_coverage_ratio, 2),
                'price_to_rent_ratio': round(self.price_to_rent_ratio, 2),
            },
            'break_even': {
                'occupancy_rate': round(self.break_even_occupancy, 2),
                'monthly_rent': round(self.break_even_rent, 2),
            },
            'rules': {
                'fifty_percent_rule': self.fifty_percent_rule_pass,
                'one_percent_rule': self.one_percent_rule_pass,
                'two_percent_rule': self.two_percent_rule_pass,
            },
            'projections': {
                'five_year_roi': round(self.five_year_roi, 2),
                'five_year_cash_flow': round(self.five_year_cash_flow, 2),
                'five_year_appreciation': round(self.five_year_appreciation, 2),
            },
            'detailed': {
                'noi_annual': round(self.noi_annual, 2),
                'effective_gross_income': round(self.effective_gross_income, 2),
                'operating_expenses_annual': round(self.operating_expenses_annual, 2),
                'mortgage_payment_annual': round(self.mortgage_payment_annual, 2),
                'total_cash_invested': round(self.total_cash_invested, 2),
            }
        }


@dataclass
class FlipAnalysis:
    """Fix and flip investment analysis"""
    purchase_price: float
    renovation_costs: float
    holding_costs_monthly: float
    expected_sale_price: float
    selling_costs_percent: float = 6.0  # Agent commissions, etc.
    holding_period_months: int = 6
    
    @property
    def total_project_cost(self) -> float:
        """Total cost of the flip project"""
        return (
            self.purchase_price +
            self.renovation_costs +
            (self.holding_costs_monthly * self.holding_period_months)
        )
    
    @property
    def net_profit(self) -> float:
        """Net profit from the flip"""
        selling_costs = self.expected_sale_price * (self.selling_costs_percent / 100)
        return self.expected_sale_price - selling_costs - self.total_project_cost
    
    @property
    def return_on_investment(self) -> float:
        """ROI percentage"""
        if self.total_project_cost == 0:
            return 0.0
        return (self.net_profit / self.total_project_cost) * 100
    
    @property
    def annualized_roi(self) -> float:
        """Annualized ROI percentage"""
        if self.holding_period_months == 0:
            return 0.0
        return self.return_on_investment * (12 / self.holding_period_months)


class InvestmentCalculator:
    """
    Professional investment calculator for real estate.
    
    Features:
    - Comprehensive ROI calculations
    - Multiple investment strategy support
    - Cash flow projections
    - Risk assessment metrics
    - Sensitivity analysis
    """
    
    def __init__(
        self,
        purchase: PurchaseDetails,
        financing: FinancingDetails,
        income: IncomeProjections,
        expenses: OperatingExpenses,
        strategy: InvestmentStrategy = InvestmentStrategy.BUY_AND_HOLD,
        appreciation_rate: float = 3.0,  # Annual appreciation
        inflation_rate: float = 2.5
    ):
        self.purchase = purchase
        self.financing = financing
        self.income = income
        self.expenses = expenses
        self.strategy = strategy
        self.appreciation_rate = appreciation_rate
        self.inflation_rate = inflation_rate
        
    def calculate(self) -> InvestmentMetrics:
        """Calculate all investment metrics"""
        metrics = InvestmentMetrics()
        
        # Calculate financing
        down_payment = self.financing.calculate_down_payment(self.purchase.purchase_price)
        
        if self.financing.financing_type != FinancingType.CASH:
            self.financing.loan_amount = self.purchase.purchase_price - down_payment
        
        monthly_mortgage = self.financing.calculate_monthly_payment()
        metrics.mortgage_payment_annual = monthly_mortgage * 12
        
        # Total cash invested
        metrics.total_cash_invested = (
            down_payment +
            self.purchase.closing_costs +
            self.purchase.renovation_costs +
            self.purchase.furniture_costs +
            self.purchase.other_costs +
            self.financing.points_upfront +
            self.financing.other_loan_costs
        )
        
        # Income
        metrics.effective_gross_income = self.income.effective_gross_income
        
        # Operating expenses
        metrics.operating_expenses_annual = self.expenses.calculate_total_annual(
            metrics.effective_gross_income,
            self.income.monthly_rent
        )
        
        # Net Operating Income (NOI)
        metrics.noi_annual = metrics.effective_gross_income - metrics.operating_expenses_annual
        
        # Cash flow
        metrics.annual_cash_flow = metrics.noi_annual - metrics.mortgage_payment_annual
        metrics.monthly_cash_flow = metrics.annual_cash_flow / 12
        
        # Cap Rate (NOI / Purchase Price)
        if self.purchase.purchase_price > 0:
            metrics.cap_rate = (metrics.noi_annual / self.purchase.purchase_price) * 100
        
        # Cash on Cash Return
        if metrics.total_cash_invested > 0:
            metrics.cash_on_cash_return = (metrics.annual_cash_flow / metrics.total_cash_invested) * 100
        
        # Gross Rent Multiplier
        if self.income.monthly_rent > 0:
            metrics.gross_rent_multiplier = self.purchase.purchase_price / (self.income.monthly_rent * 12)
        
        # Debt Service Coverage Ratio
        if metrics.mortgage_payment_annual > 0:
            metrics.debt_service_coverage_ratio = metrics.noi_annual / metrics.mortgage_payment_annual
        
        # Price to Rent Ratio
        if self.income.monthly_rent > 0:
            metrics.price_to_rent_ratio = self.purchase.purchase_price / self.income.monthly_rent
        
        # Break-even analysis
        total_fixed_costs = (
            self.expenses.property_tax_annual +
            self.expenses.insurance_annual +
            (self.expenses.hoa_fees_monthly * 12) +
            (self.expenses.utilities_monthly * 12) +
            metrics.mortgage_payment_annual
        )
        
        variable_expense_rate = (
            self.expenses.property_management_percent +
            self.expenses.maintenance_percent +
            self.expenses.capex_reserve_percent
        ) / 100
        
        # Break-even occupancy
        if metrics.effective_gross_income > 0:
            metrics.break_even_occupancy = (
                total_fixed_costs / 
                (self.income.monthly_rent * 12 * (1 - variable_expense_rate))
            ) * 100
        
        # Break-even rent
        if (1 - variable_expense_rate) > 0:
            metrics.break_even_rent = total_fixed_costs / (12 * (1 - variable_expense_rate))
        
        # 50% Rule check
        metrics.fifty_percent_rule_estimate = metrics.effective_gross_income * 0.5
        actual_expenses_with_mortgage = metrics.operating_expenses_annual + metrics.mortgage_payment_annual
        metrics.fifty_percent_rule_pass = actual_expenses_with_mortgage <= metrics.fifty_percent_rule_estimate
        
        # 1% and 2% Rules
        monthly_rent = self.income.monthly_rent
        purchase_price = self.purchase.purchase_price
        
        if purchase_price > 0:
            rent_ratio = (monthly_rent / purchase_price) * 100
            metrics.one_percent_rule_pass = rent_ratio >= 1.0
            metrics.two_percent_rule_pass = rent_ratio >= 2.0
        
        # 5-year projection
        metrics.five_year_cash_flow = self._project_cash_flow(years=5)
        metrics.five_year_appreciation = self._project_appreciation(years=5)
        metrics.five_year_roi = self._calculate_five_year_roi(metrics)
        
        return metrics
    
    def _project_cash_flow(self, years: int = 5) -> float:
        """Project cash flow over multiple years"""
        total_cash_flow = 0.0
        
        current_rent = self.income.monthly_rent
        current_expenses = self.expenses
        
        for year in range(1, years + 1):
            # Increase rent
            current_rent *= (1 + self.income.annual_rent_increase / 100)
            
            # Calculate annual cash flow for this year
            annual_rent = current_rent * 12
            vacancy_loss = annual_rent * (self.income.vacancy_rate / 100)
            egi = annual_rent - vacancy_loss
            
            # Expenses increase with inflation
            expenses_multiplier = (1 + self.inflation_rate / 100) ** year
            
            operating_expenses = (
                current_expenses.property_tax_annual * expenses_multiplier +
                current_expenses.insurance_annual * expenses_multiplier +
                egi * (current_expenses.property_management_percent / 100) +
                egi * (current_expenses.maintenance_percent / 100) +
                egi * (current_expenses.capex_reserve_percent / 100) +
                current_expenses.utilities_monthly * 12 * expenses_multiplier +
                current_expenses.hoa_fees_monthly * 12 * expenses_multiplier
            )
            
            noi = egi - operating_expenses
            annual_cf = noi - self.financing.calculate_monthly_payment() * 12
            total_cash_flow += annual_cf
        
        return total_cash_flow
    
    def _project_appreciation(self, years: int = 5) -> float:
        """Project property appreciation"""
        future_value = self.purchase.purchase_price * (
            (1 + self.appreciation_rate / 100) ** years
        )
        return future_value - self.purchase.purchase_price
    
    def _calculate_five_year_roi(self, metrics: InvestmentMetrics) -> float:
        """Calculate 5-year ROI including appreciation"""
        total_return = (
            metrics.five_year_cash_flow +
            metrics.five_year_appreciation
        )
        
        if metrics.total_cash_invested > 0:
            return (total_return / metrics.total_cash_invested) * 100
        return 0.0
    
    def sensitivity_analysis(
        self,
        rent_variations: List[float] = None,
        expense_variations: List[float] = None
    ) -> Dict[str, Any]:
        """
        Perform sensitivity analysis on key variables.
        
        Args:
            rent_variations: List of rent multipliers (e.g., [0.9, 1.0, 1.1])
            expense_variations: List of expense multipliers
            
        Returns:
            Dictionary with sensitivity results
        """
        if rent_variations is None:
            rent_variations = [0.8, 0.9, 1.0, 1.1, 1.2]
        if expense_variations is None:
            expense_variations = [0.8, 0.9, 1.0, 1.1, 1.2]
        
        results = {
            'rent_sensitivity': {},
            'expense_sensitivity': {},
            'combined_scenarios': []
        }
        
        base_metrics = self.calculate()
        
        # Rent sensitivity
        original_rent = self.income.monthly_rent
        for variation in rent_variations:
            self.income.monthly_rent = original_rent * variation
            metrics = self.calculate()
            results['rent_sensitivity'][f"{variation*100:.0f}%"] = {
                'monthly_rent': round(self.income.monthly_rent, 2),
                'cash_on_cash_return': round(metrics.cash_on_cash_return, 2),
                'monthly_cash_flow': round(metrics.monthly_cash_flow, 2),
            }
        self.income.monthly_rent = original_rent
        
        # Expense sensitivity
        original_expenses = {
            'property_tax': self.expenses.property_tax_annual,
            'insurance': self.expenses.insurance_annual,
            'utilities': self.expenses.utilities_monthly,
            'hoa': self.expenses.hoa_fees_monthly,
        }
        
        for variation in expense_variations:
            self.expenses.property_tax_annual = original_expenses['property_tax'] * variation
            self.expenses.insurance_annual = original_expenses['insurance'] * variation
            self.expenses.utilities_monthly = original_expenses['utilities'] * variation
            self.expenses.hoa_fees_monthly = original_expenses['hoa'] * variation
            
            metrics = self.calculate()
            results['expense_sensitivity'][f"{variation*100:.0f}%"] = {
                'annual_expenses': round(metrics.operating_expenses_annual, 2),
                'cash_on_cash_return': round(metrics.cash_on_cash_return, 2),
                'monthly_cash_flow': round(metrics.monthly_cash_flow, 2),
            }
        
        # Restore original expenses
        self.expenses.property_tax_annual = original_expenses['property_tax']
        self.expenses.insurance_annual = original_expenses['insurance']
        self.expenses.utilities_monthly = original_expenses['utilities']
        self.expenses.hoa_fees_monthly = original_expenses['hoa']
        
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive investment analysis report"""
        metrics = self.calculate()
        sensitivity = self.sensitivity_analysis()
        
        return {
            'property_summary': {
                'purchase_price': self.purchase.purchase_price,
                'total_investment': self.purchase.total_investment,
                'strategy': self.strategy.value,
                'financing_type': self.financing.financing_type.value,
            },
            'income_analysis': {
                'monthly_rent': self.income.monthly_rent,
                'effective_gross_income': metrics.effective_gross_income,
                'vacancy_rate': self.income.vacancy_rate,
            },
            'expense_breakdown': {
                'property_tax': self.expenses.property_tax_annual,
                'insurance': self.expenses.insurance_annual,
                'property_management': metrics.effective_gross_income * (self.expenses.property_management_percent / 100),
                'maintenance': metrics.effective_gross_income * (self.expenses.maintenance_percent / 100),
                'capex_reserve': metrics.effective_gross_income * (self.expenses.capex_reserve_percent / 100),
                'utilities': self.expenses.utilities_monthly * 12,
                'hoa_fees': self.expenses.hoa_fees_monthly * 12,
                'total_operating_expenses': metrics.operating_expenses_annual,
            },
            'financing_details': {
                'down_payment': self.financing.calculate_down_payment(self.purchase.purchase_price),
                'loan_amount': self.financing.loan_amount,
                'interest_rate': self.financing.interest_rate,
                'monthly_payment': self.financing.calculate_monthly_payment(),
                'total_cash_invested': metrics.total_cash_invested,
            },
            'performance_metrics': metrics.to_dict(),
            'sensitivity_analysis': sensitivity,
            'recommendations': self._generate_recommendations(metrics),
            'generated_at': datetime.utcnow().isoformat(),
        }
    
    def _generate_recommendations(self, metrics: InvestmentMetrics) -> List[str]:
        """Generate investment recommendations based on metrics"""
        recommendations = []
        
        if metrics.cash_on_cash_return < 0:
            recommendations.append(
                "⚠️ Negative cash flow - consider negotiating price or increasing rent"
            )
        elif metrics.cash_on_cash_return < 5:
            recommendations.append(
                "📊 Low cash-on-cash return - evaluate if appreciation potential justifies investment"
            )
        elif metrics.cash_on_cash_return > 10:
            recommendations.append(
                "✅ Strong cash-on-cash return - good cash flow investment"
            )
        
        if metrics.cap_rate < 4:
            recommendations.append(
                "📉 Low cap rate - typical for premium markets, rely on appreciation"
            )
        elif metrics.cap_rate > 8:
            recommendations.append(
                "📈 High cap rate - strong income potential, verify market stability"
            )
        
        if not metrics.one_percent_rule_pass:
            recommendations.append(
                "💡 Fails 1% rule - rent may be below market or price too high"
            )
        
        if metrics.debt_service_coverage_ratio < 1.2:
            recommendations.append(
                "⚠️ Low DSCR - limited buffer for vacancy or expenses"
            )
        
        if metrics.monthly_cash_flow < 100:
            recommendations.append(
                "💰 Thin cash flow margin - ensure adequate reserves"
            )
        
        return recommendations


class FlipCalculator:
    """Calculator for fix and flip investments"""
    
    @staticmethod
    def calculate(
        purchase_price: float,
        renovation_costs: float,
        expected_sale_price: float,
        holding_costs_monthly: float = 500,
        holding_period_months: int = 6,
        selling_costs_percent: float = 6.0,
        financing_costs: float = 0.0
    ) -> FlipAnalysis:
        """Calculate fix and flip metrics"""
        return FlipAnalysis(
            purchase_price=purchase_price,
            renovation_costs=renovation_costs,
            holding_costs_monthly=holding_costs_monthly,
            expected_sale_price=expected_sale_price,
            selling_costs_percent=selling_costs_percent,
            holding_period_months=holding_period_months
        )
    
    @staticmethod
    def maximum_allowable_offer(
        expected_sale_price: float,
        renovation_costs: float,
        desired_profit: float,
        holding_costs_monthly: float = 500,
        holding_period_months: int = 6,
        selling_costs_percent: float = 6.0
    ) -> float:
        """Calculate maximum offer price for desired profit"""
        selling_costs = expected_sale_price * (selling_costs_percent / 100)
        holding_costs = holding_costs_monthly * holding_period_months
        
        mao = (
            expected_sale_price -
            selling_costs -
            renovation_costs -
            holding_costs -
            desired_profit
        )
        
        return max(0, mao)


# Convenience functions

def analyze_rental_property(
    purchase_price: float,
    monthly_rent: float,
    property_tax_annual: float = 0.0,
    insurance_annual: float = 0.0,
    hoa_monthly: float = 0.0,
    down_payment_percent: float = 25.0,
    interest_rate: float = 6.5,
    **kwargs
) -> Dict[str, Any]:
    """
    Quick analysis of a rental property.
    
    Args:
        purchase_price: Property purchase price
        monthly_rent: Expected monthly rent
        property_tax_annual: Annual property tax
        insurance_annual: Annual insurance cost
        hoa_monthly: Monthly HOA fees
        down_payment_percent: Down payment percentage
        interest_rate: Mortgage interest rate
        
    Returns:
        Investment analysis report
    """
    purchase = PurchaseDetails(
        purchase_price=purchase_price,
        closing_costs=purchase_price * 0.03,  # Estimate 3% closing costs
    )
    
    financing = FinancingDetails(
        financing_type=FinancingType.CONVENTIONAL_MORTGAGE,
        down_payment_percent=down_payment_percent,
        interest_rate=interest_rate,
    )
    
    income = IncomeProjections(monthly_rent=monthly_rent)
    
    expenses = OperatingExpenses(
        property_tax_annual=property_tax_annual,
        insurance_annual=insurance_annual,
        hoa_fees_monthly=hoa_monthly,
    )
    
    calculator = InvestmentCalculator(
        purchase=purchase,
        financing=financing,
        income=income,
        expenses=expenses
    )
    
    return calculator.generate_report()
