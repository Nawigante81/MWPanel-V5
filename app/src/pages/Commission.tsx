import { useMemo, useState, useEffect } from 'react';
import { 
  Calculator, 
  TrendingUp, 
  DollarSign, 
  Percent, 
  Building2,
  User,
  Download,
  History,
  Save,
  Trash2,
  RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { toast } from 'sonner';


interface CommissionCalculation {
  id: string;
  date: string;
  propertyValue: number;
  commissionRate: number;
  grossCommission: number;
  officeFee: number;
  netCommission: number;
  propertyType: string;
  clientName: string;
  notes?: string;
}

const propertyTypes = [
  { value: 'apartment', label: 'Mieszkanie', defaultRate: 2.5 },
  { value: 'house', label: 'Dom', defaultRate: 3.0 },
  { value: 'land', label: 'Działka', defaultRate: 4.0 },
  { value: 'commercial', label: 'Lokal użytkowy', defaultRate: 3.5 },
  { value: 'garage', label: 'Garaż', defaultRate: 5.0 },
];

const officeFeeTiers = [
  { max: 10000, rate: 30 },
  { max: 25000, rate: 25 },
  { max: 50000, rate: 20 },
  { max: Infinity, rate: 15 },
];

function calculateOfficeFee(grossCommission: number): number {
  const tier = officeFeeTiers.find(t => grossCommission <= t.max) || officeFeeTiers[officeFeeTiers.length - 1];
  return (grossCommission * tier.rate) / 100;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pl-PL', {
    style: 'currency',
    currency: 'PLN',
    maximumFractionDigits: 0,
  }).format(value);
}

export default function Commission() {
  const [propertyValue, setPropertyValue] = useState<string>('500000');
  const [commissionRate, setCommissionRate] = useState<string>('2.5');
  const [propertyType, setPropertyType] = useState<string>('apartment');
  const [clientName, setClientName] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [history, setHistory] = useState<CommissionCalculation[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Load history from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('commissionHistory');
    if (saved) {
      setHistory(JSON.parse(saved));
    }
  }, []);

  // Save history to localStorage
  useEffect(() => {
    localStorage.setItem('commissionHistory', JSON.stringify(history));
  }, [history]);

  const value = parseFloat(propertyValue) || 0;
  const rate = parseFloat(commissionRate) || 0;

  const calculated = useMemo(() => {
    const grossCommission = (value * rate) / 100;
    const officeFee = calculateOfficeFee(grossCommission);
    const netCommission = grossCommission - officeFee;
    const vatAmount = netCommission * 0.23;
    const finalAmount = netCommission - vatAmount;
    return { grossCommission, officeFee, netCommission, vatAmount, finalAmount };
  }, [value, rate]);

  const [manualCalc, setManualCalc] = useState(calculated);

  useEffect(() => {
    // keep defaults in sync initially
    setManualCalc(calculated);
  }, [calculated.grossCommission, calculated.officeFee, calculated.netCommission, calculated.vatAmount, calculated.finalAmount]);

  const recalcCommission = () => {
    if (!rate || rate <= 0) {
      toast.error('Najpierw wybierz stawkę prowizji.');
      return;
    }
    if (!value || value <= 0) {
      toast.error('Wartość nieruchomości musi być większa od 0.');
      return;
    }
    setManualCalc(calculated);
    toast.success('Prowizja przeliczona');
  };

  const grossCommission = manualCalc.grossCommission;
  const officeFee = manualCalc.officeFee;
  const netCommission = manualCalc.netCommission;
  const vatAmount = manualCalc.vatAmount; // 23% VAT
  const finalAmount = manualCalc.finalAmount;

  const handlePropertyTypeChange = (type: string) => {
    setPropertyType(type);
    const selectedType = propertyTypes.find(t => t.value === type);
    if (selectedType) {
      setCommissionRate(selectedType.defaultRate.toString());
    }
  };

  const saveCalculation = () => {
    if (!propertyValue || !commissionRate) return;
    
    const newCalculation: CommissionCalculation = {
      id: Date.now().toString(),
      date: new Date().toISOString(),
      propertyValue: value,
      commissionRate: rate,
      grossCommission,
      officeFee,
      netCommission,
      propertyType: propertyTypes.find(t => t.value === propertyType)?.label || '',
      clientName: clientName || 'Nieznany klient',
      notes,
    };
    
    setHistory(prev => [newCalculation, ...prev].slice(0, 50));
  };

  const deleteCalculation = (id: string) => {
    setHistory(prev => prev.filter(c => c.id !== id));
  };

  const clearHistory = () => {
    setHistory([]);
  };

  const exportHistory = () => {
    const csv = [
      ['Data', 'Klient', 'Typ', 'Wartość', 'Stawka %', 'Prowizja brutto', 'Opłata biura', 'Netto'].join(';'),
      ...history.map(c => [
        new Date(c.date).toLocaleDateString('pl-PL'),
        c.clientName,
        c.propertyType,
        c.propertyValue,
        c.commissionRate,
        c.grossCommission.toFixed(2),
        c.officeFee.toFixed(2),
        c.netCommission.toFixed(2),
      ].join(';'))
    ].join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `prowizje_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Kalkulator prowizji</h1>
          <p className="text-muted-foreground">
            Oblicz prowizję od transakcji i śledź historię wyliczeń
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setShowHistory(!showHistory)}>
            <History className="w-4 h-4 mr-2" />
            Historia
          </Button>
          <Button variant="outline" onClick={exportHistory}>
            <Download className="w-4 h-4 mr-2" />
            Eksport
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Calculator */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="w-5 h-5" />
                Dane transakcji
              </CardTitle>
              <CardDescription>
                Wprowadź dane, aby obliczyć prowizję
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Property Type */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Typ nieruchomości</label>
                <Select value={propertyType} onValueChange={handlePropertyTypeChange}>
                  <SelectTrigger>
                    <Building2 className="w-4 h-4 mr-2" />
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {propertyTypes.map(type => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label} (domyślnie {type.defaultRate}%)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Property Value */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Wartość nieruchomości</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    type="number"
                    value={propertyValue}
                    onChange={(e) => setPropertyValue(e.target.value)}
                    className="pl-10"
                    placeholder="500000"
                  />
                </div>
              </div>

              {/* Commission Rate */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Stawka prowizji (%)</label>
                <div className="relative">
                  <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    type="number"
                    step="0.1"
                    value={commissionRate}
                    onChange={(e) => setCommissionRate(e.target.value)}
                    className="pl-10"
                    placeholder="2.5"
                  />
                </div>
                <div className="flex gap-2 flex-wrap">
                  {[1.5, 2.0, 2.5, 3.0, 3.5, 4.0].map(rate => (
                    <Button
                      key={rate}
                      variant={commissionRate === rate.toString() ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setCommissionRate(rate.toString())}
                    >
                      {rate}%
                    </Button>
                  ))}
                </div>
                <Button
                  variant="outline"
                  onClick={recalcCommission}
                  disabled={!(rate > 0 && value > 0)}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Przelicz prowizję
                </Button>
              </div>

              {/* Client Name */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Klient (opcjonalnie)</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    value={clientName}
                    onChange={(e) => setClientName(e.target.value)}
                    className="pl-10"
                    placeholder="Imię i nazwisko klienta"
                  />
                </div>
              </div>

              {/* Notes */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Notatki (opcjonalnie)</label>
                <Input
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Dodatkowe informacje..."
                />
              </div>

              <Button onClick={saveCalculation} className="w-full">
                <Save className="w-4 h-4 mr-2" />
                Zapisz kalkulację
              </Button>
            </CardContent>
          </Card>

          {/* History */}
          {showHistory && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Historia kalkulacji</CardTitle>
                  <CardDescription>Ostatnie {history.length} obliczeń</CardDescription>
                </div>
                <Button variant="destructive" size="sm" onClick={clearHistory}>
                  <Trash2 className="w-4 h-4 mr-2" />
                  Wyczyść
                </Button>
              </CardHeader>
              <CardContent>
                {history.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    Brak zapisanych kalkulacji
                  </p>
                ) : (
                  <div className="space-y-2">
                    {history.map(calc => (
                      <div 
                        key={calc.id} 
                        className="flex items-center justify-between p-3 rounded-lg border hover:bg-accent/50 transition-colors"
                      >
                        <div>
                          <p className="font-medium">{calc.clientName}</p>
                          <p className="text-sm text-muted-foreground">
                            {calc.propertyType} • {formatCurrency(calc.propertyValue)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(calc.date).toLocaleDateString('pl-PL')}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-bold text-lg">{formatCurrency(calc.netCommission)}</p>
                          <p className="text-sm text-muted-foreground">
                            netto ({calc.commissionRate}%)
                          </p>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="icon"
                          onClick={() => deleteCalculation(calc.id)}
                        >
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Results */}
        <div className="space-y-6">
          <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Wynik kalkulacji
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Gross Commission */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Prowizja brutto</span>
                  <Badge variant="secondary">{rate}% z {formatCurrency(value)}</Badge>
                </div>
                <p className="text-3xl font-bold">{formatCurrency(grossCommission)}</p>
              </div>

              <Separator />

              {/* Office Fee */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Opłata biura</span>
                  <Badge variant="outline">
                    {officeFeeTiers.find(t => grossCommission <= t.max)?.rate || 15}%
                  </Badge>
                </div>
                <p className="text-xl font-semibold text-amber-600">-{formatCurrency(officeFee)}</p>
              </div>

              <Separator />

              {/* Net Commission */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Prowizja netto</span>
                </div>
                <p className="text-2xl font-bold text-emerald-600">{formatCurrency(netCommission)}</p>
              </div>

              <Separator />

              {/* VAT */}
              <Accordion type="single" collapsible>
                <AccordionItem value="vat">
                  <AccordionTrigger className="text-sm">
                    <span className="text-muted-foreground">Podatek VAT (23%)</span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <p className="text-lg font-semibold text-rose-600">-{formatCurrency(vatAmount)}</p>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>

              <Separator />

              {/* Final Amount */}
              <div className="space-y-2 p-4 bg-primary/10 rounded-xl">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">Kwota na rękę</span>
                </div>
                <p className="text-4xl font-bold text-primary">{formatCurrency(finalAmount)}</p>
              </div>
            </CardContent>
          </Card>

          {/* Fee Structure Info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Struktura opłat biura</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {officeFeeTiers.map((tier, i) => (
                  <div key={i} className="flex justify-between">
                    <span className="text-muted-foreground">
                      {i === 0 ? `Do ${tier.max.toLocaleString('pl-PL')} zł` :
                       tier.max === Infinity ? `Powyżej ${officeFeeTiers[i-1].max.toLocaleString('pl-PL')} zł` :
                       `Do ${tier.max.toLocaleString('pl-PL')} zł`}
                    </span>
                    <span className="font-medium">{tier.rate}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Quick Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Podsumowanie miesiąca</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Liczba transakcji</span>
                <span className="font-medium">{history.filter(h => new Date(h.date).getMonth() === new Date().getMonth()).length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Suma prowizji</span>
                <span className="font-medium">
                  {formatCurrency(history
                    .filter(h => new Date(h.date).getMonth() === new Date().getMonth())
                    .reduce((sum, h) => sum + h.netCommission, 0))}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Średnia transakcja</span>
                <span className="font-medium">
                  {formatCurrency(
                    history.filter(h => new Date(h.date).getMonth() === new Date().getMonth()).length > 0
                      ? history
                          .filter(h => new Date(h.date).getMonth() === new Date().getMonth())
                          .reduce((sum, h) => sum + h.netCommission, 0) /
                        history.filter(h => new Date(h.date).getMonth() === new Date().getMonth()).length
                      : 0
                  )}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
