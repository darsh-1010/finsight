import { AlertTriangle, ShieldCheck, Info } from 'lucide-react';
import React from 'react';

import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';

interface ComplianceModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const RiskDisclosure = () => (
  <section className="space-y-3">
    <h3 className="text-lg font-semibold flex items-center gap-2">
      <AlertTriangle className="h-5 w-5 text-indigo-500" />
        Risk Disclosure
    </h3>
    <p className="text-sm text-muted-foreground leading-relaxed">
        Trading and investing in financial markets involves significant risk of loss and is not suitable 
        for every investor. The valuation of financial instruments may fluctuate, and as a result, 
        clients may lose more than their original investment. 
    </p>
  </section>
);

const NoFinancialAdvice = () => (
  <section className="space-y-3">
    <h3 className="text-lg font-semibold flex items-center gap-2">
      <Info className="h-5 w-5 text-blue-500" />
        No Financial Advice
    </h3>
    <p className="text-sm text-muted-foreground leading-relaxed">
        The information provided by FinSight is for educational and informational purposes only and 
        should not be construed as investment, financial, or legal advice. 
        FinSight is an AI-powered insights tool, not a registered investment advisor.
    </p>
  </section>
);

const UserResponsibility = () => (
  <section className="space-y-3">
    <h3 className="text-lg font-semibold flex items-center gap-2">
      <ShieldCheck className="h-5 w-5 text-green-500" />
        User Responsibility
    </h3>
    <p className="text-sm text-muted-foreground leading-relaxed">
        You acknowledge that you are responsible for your own investment decisions. 
        You should consult with a qualified professional before making any financial decisions 
        based on the insights provided by this platform.
    </p>
  </section>
);

const ComplianceModal: React.FC<ComplianceModalProps> = ({ isOpen, onClose }) => (
  <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
    <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <div className="w-12 h-12 bg-indigo-500/10 rounded-xl flex items-center justify-center mb-4 border border-indigo-500/20">
          <ShieldCheck className="h-6 w-6 text-indigo-500" />
        </div>
        <DialogTitle className="text-2xl font-bold">
            Compliance Disclosures & User Acknowledgements
        </DialogTitle>
        <DialogDescription className="text-base pt-2">
            Please read and acknowledge the following disclosures before proceeding to the dashboard.
        </DialogDescription>
      </DialogHeader>

      <div className="py-4 space-y-6">
        <RiskDisclosure />
        <NoFinancialAdvice />
        <UserResponsibility />
      </div>

      <DialogFooter className="pt-4">
        <Button 
          onClick={onClose} 
          className="w-full py-6 text-lg font-bold rounded-xl shadow-lg hover:scale-[1.02] active:scale-[0.98] transition-all bg-primary text-white"
        >
            I Acknowledge and Agree
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

export { ComplianceModal };
