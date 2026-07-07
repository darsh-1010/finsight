import { User, Mail, RefreshCw } from 'lucide-react';
import React, { useState } from 'react';
import { PiChartBar, PiWarningCircle } from 'react-icons/pi';

import { authApi } from '@/api/auth';
import type { User as UserInterface } from '@/api/auth';
import { useAlert } from '@/context/AlertContext';

interface PersonalInfoProps {
  user: UserInterface | null;
  embedded?: boolean;
}

/* -------------------- Sub Components -------------------- */

const InfoField = ({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) => (
  <div>
    <label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">
      {label}
    </label>
    <div className="mt-1">{children}</div>
  </div>
);

const IconText = ({
  icon,
  text,
  capitalize = false,
}: {
  icon: React.ReactNode;
  text: string;
  capitalize?: boolean;
}) => (
  <div className="flex items-center gap-2">
    {icon}
    <p className={`font-semibold text-lg ${capitalize ? 'capitalize' : ''}`}>
      {text}
    </p>
  </div>
);

const BioSection = () => (
  <div className="pt-4 border-t border-border/50">
    <label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">
      Bio
    </label>
    <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
      AI-powered trading enthusiast and market analyst. Dedicated to mastering
      the art of algorithmic strategies and staying ahead in the ever-evolving
      world of digital finance.
    </p>
  </div>
);

/* -------------------- Main Component -------------------- */

const PersonalInfo: React.FC<PersonalInfoProps> = ({ user, embedded = false }) => {
  const name = user?.email?.split('@')[0] || 'User Name';
  const email = user?.email || 'user@example.com';
  const experience = user?.experience_level || 'Not set';
  const risk = user?.risk_level || 'Not set';
  const is_verified = user?.is_verified ?? false;

  const content = (
    <div className="space-y-6">
      <PrimaryInfo name={name} email={email} is_verified={is_verified} />
      <SecondaryInfo experience={experience} risk={risk} />
      <BioSection />
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <section className="bg-card border border-border p-6 rounded-2xl neon-card">
      <Header />
      {content}
    </section>
  );
};

/* -------------------- Sections -------------------- */

const Header = () => (
  <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
    <User size={20} className="text-primary" />
    Personal Information
  </h2>
);

const PrimaryInfo = ({ name, email, is_verified }: { name: string; email: string; is_verified: boolean }) => {
  const { showAlert } = useAlert();
  const [isResending, setIsResending] = useState(false);

  const handleResend = async () => {
    setIsResending(true);
    try {
      await authApi.resendVerification();
      showAlert('Success', 'Verification email sent successfully. Please check your inbox.');
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to send verification email.');
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      <InfoField label="Full Name">
        <p className="font-semibold text-lg">{name}</p>
      </InfoField>

      <InfoField label="Email Address">
        <div className="flex flex-wrap items-center gap-3">
          <IconText
            icon={<Mail size={18} className="text-primary/60" />}
            text={email}
          />
          {is_verified ? (
            <span className="bg-green-500/10 text-green-500 text-xs px-2 py-0.5 rounded-full font-medium border border-green-500/20 whitespace-nowrap">Verified</span>
          ) : (
            <div className="flex flex-wrap items-center gap-2 mt-1 sm:mt-0">
              <span className="bg-yellow-500/10 text-yellow-500 text-xs px-2 py-0.5 rounded-full font-medium border border-yellow-500/20 whitespace-nowrap">Unverified</span>
              <button
                onClick={handleResend}
                disabled={isResending}
                className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors disabled:opacity-50 whitespace-nowrap"
                title="Resend verification email"
              >
                <RefreshCw size={12} className={isResending ? 'animate-spin' : ''} />
                {isResending ? 'Sending...' : 'Resend'}
              </button>
            </div>
          )}
        </div>
      </InfoField>
    </div>
  );
};

const SecondaryInfo = ({
  experience,
  risk,
}: {
  experience: string;
  risk: string;
}) => (
  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-border/50">
    <InfoField label="Experience Level">
      <IconText
        icon={<PiChartBar size={18} className="text-primary/60" />}
        text={experience}
        capitalize
      />
    </InfoField>

    <InfoField label="Risk Level">
      <IconText
        icon={<PiWarningCircle size={18} className="text-primary/60" />}
        text={risk}
        capitalize
      />
    </InfoField>
  </div>
);

export default PersonalInfo;
