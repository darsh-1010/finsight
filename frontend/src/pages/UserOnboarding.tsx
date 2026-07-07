import {
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  ChevronDown,
  Check,
  Loader2,
  LogOut,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useUserOnboarding } from '@/hooks/useUserOnboarding';
import { cn } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';

/* ---------------- TYPES ---------------- */

type Option = string | Record<string, unknown>;

interface Question {
  id: number;
  question_text: string;
  question_type: string;
  options: Option[];
}

interface Answer {
  value: string;
}

/* ---------------- HEADER ---------------- */

const OnboardingHeader: React.FC<{ question: Question }> = ({ question }) => (
  <div className="mb-8">
    <h2 className="text-xl font-bold">{question.question_text}</h2>
  </div>
);

/* ---------------- DROPDOWN ITEM ---------------- */

const DropdownItem: React.FC<{
  option: Option;
  question: Question;
  selectedAnswer?: Answer;
  handleOptionSelect: (opt: Option, id: number, type: string) => void;
  getOptionLabel: (opt: Option) => string;
  getOptionValue: (opt: Option) => string;
}> = ({
  option,
  question,
  selectedAnswer,
  handleOptionSelect,
  getOptionLabel,
  getOptionValue,
}) => {
  const label = getOptionLabel(option);
  const value = getOptionValue(option);

  return (
    <CommandItem
      onSelect={() => handleOptionSelect(option, question.id, question.question_type)
      }
    >
      <Check
        className={cn(
          'mr-2',
          selectedAnswer?.value === value ? 'opacity-100' : 'opacity-0',
        )}
      />
      {label}
    </CommandItem>
  );
};

/* ---------------- DROPDOWN ---------------- */

const DropdownOptions: React.FC<{
  question: Question;
  selectedAnswer?: Answer;
  open: boolean;
  setOpen: (v: boolean) => void;
  handleOptionSelect: (opt: Option, id: number, type: string) => void;
  getOptionLabel: (opt: Option) => string;
  getOptionValue: (opt: Option) => string;
}> = ({
  question,
  selectedAnswer,
  open,
  setOpen,
  handleOptionSelect,
  getOptionLabel,
  getOptionValue,
}) => (
  <Popover open={open} onOpenChange={setOpen}>
    <PopoverTrigger asChild>
      <Button
        variant="outline"
        className="w-full h-auto p-4 rounded-xl flex justify-between font-normal"
      >
        {selectedAnswer?.value || 'Select...'}
        <ChevronDown className="opacity-50" />
      </Button>
    </PopoverTrigger>

    <PopoverContent className="p-0">
      <Command>
        <CommandInput placeholder="Search..." />
        <CommandList>
          <CommandEmpty>No results</CommandEmpty>
          <CommandGroup>
            {question.options?.map((opt, i) => (
              <DropdownItem
                key={i}
                option={opt}
                question={question}
                selectedAnswer={selectedAnswer}
                handleOptionSelect={handleOptionSelect}
                getOptionLabel={getOptionLabel}
                getOptionValue={getOptionValue}
              />
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </PopoverContent>
  </Popover>
);

/* ---------------- BUTTON OPTION ITEM ---------------- */

const ButtonOptionItem: React.FC<{
  option: Option;
  question: Question;
  selectedAnswer?: Answer;
  handleOptionSelect: (opt: Option, id: number, type: string) => void;
  getOptionLabel: (opt: Option) => string;
  getOptionValue: (opt: Option) => string;
}> = ({
  option,
  question,
  selectedAnswer,
  handleOptionSelect,
  getOptionLabel,
  getOptionValue,
}) => {
  const label = getOptionLabel(option);
  const value = getOptionValue(option);
  const active = selectedAnswer?.value === value;

  return (
    <button
      onClick={() =>
        handleOptionSelect(option, question.id, question.question_type)
      }
      className={cn(
        'p-4 border rounded-xl text-left transition-all',
        'hover:bg-accent hover:text-accent-foreground',
        active ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-border bg-card',
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium">{label}</span>
        {active && <CheckCircle2 className="w-5 h-5 text-primary" />}
      </div>
    </button>
  );
};

/* ---------------- BUTTON OPTIONS ---------------- */

const ButtonOptions: React.FC<{
  question: Question;
  selectedAnswer?: Answer;
  handleOptionSelect: (opt: Option, id: number, type: string) => void;
  getOptionLabel: (opt: Option) => string;
  getOptionValue: (opt: Option) => string;
}> = ({
  question,
  selectedAnswer,
  handleOptionSelect,
  getOptionLabel,
  getOptionValue,
}) => (
  <div className="grid gap-3">
    {question.options?.map((opt, i) => (
      <ButtonOptionItem
        key={i}
        option={opt}
        question={question}
        selectedAnswer={selectedAnswer}
        handleOptionSelect={handleOptionSelect}
        getOptionLabel={getOptionLabel}
        getOptionValue={getOptionValue}
      />
    ))}
  </div>
);

/* ---------------- FOOTER ---------------- */

const OnboardingFooter: React.FC<{
  currentStep: number;
  handleBack: () => void;
  handleNext: (total: number, cb: () => void) => void;
  totalQuestions: number;
  handleComplete: () => void;
  selectedAnswer?: Answer;
  isSubmitting: boolean;
}> = ({
  currentStep,
  handleBack,
  handleNext,
  totalQuestions,
  handleComplete,
  selectedAnswer,
  isSubmitting,
}) => (
  <div className="flex justify-between mt-8 pt-4 border-t">
    <Button
      variant="ghost"
      onClick={handleBack}
      disabled={currentStep === 0}
      className={cn(
        "flex items-center gap-2",
        currentStep === 0 && "invisible"
      )}
    >
      <ChevronLeft className="w-4 h-4" /> Back
    </Button>

    <Button
      onClick={() => handleNext(totalQuestions, handleComplete)}
      disabled={!selectedAnswer || isSubmitting}
      className="min-w-[120px]"
    >
      {isSubmitting ? (
        <Loader2 className="animate-spin w-4 h-4" />
      ) : (
        <>
          Next <ChevronRight className="w-4 h-4" />
        </>
      )}
    </Button>
  </div>
);

type Props = {
  state: ReturnType<typeof useUserOnboarding>;
  logout?: () => void;
};

const AnimatedBackground = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
    <div className="absolute -top-[25%] -left-[10%] w-[50%] h-[50%] rounded-full bg-primary/20 blur-[120px] animate-pulse mix-blend-screen" style={{ animationDuration: '8s' }}></div>
    <div className="absolute top-[40%] -right-[10%] w-[50%] h-[60%] rounded-full bg-blue-600/20 blur-[120px] animate-pulse mix-blend-screen" style={{ animationDuration: '12s' }}></div>
    <div className="absolute -bottom-[20%] left-[20%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px] animate-pulse mix-blend-screen" style={{ animationDuration: '10s' }}></div>
  </div>
);

const OnboardingLayout: React.FC<{
  progress: number;
  children: React.ReactNode;
  logout?: () => void;
}> = ({ progress, children, logout }) => (
  <div className="min-h-screen flex flex-col items-center p-4 bg-background relative overflow-hidden pt-12 md:pt-20">
    <AnimatedBackground />

    {logout && (
      <div className="absolute top-4 right-4 md:top-8 md:right-8 z-50">
        <Button 
          variant="ghost" 
          onClick={logout}
          className="text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors rounded-xl p-2 md:px-4 md:py-2 flex items-center gap-2"
          title="Log out"
        >
          <LogOut className="w-5 h-5 md:hidden" />
          <span className="hidden md:inline text-sm">Log out</span>
        </Button>
      </div>
    )}
    
    <div className="w-full max-w-3xl relative z-10 flex flex-col items-center">
      <div className="mb-10 text-center">
        <h1 className="text-4xl md:text-5xl font-logo tracking-tight">FinSight</h1>
      </div>
      
      <div className="w-full max-w-xl mb-12">
        <ProgressBar progress={progress} />
      </div>

      <div className="w-full max-w-2xl px-4 md:px-0">
        {children}
      </div>
    </div>
  </div>
);

const UserOnboardingView: React.FC<Props> = ({ state, logout }) => {
  const {
    currentStep,
    answers,
    open,
    setOpen,
    isSubmitting,
    questions,
    handleOptionSelect,
    handleNext,
    handleBack,
    handleComplete,
    getOptionLabel,
    getOptionValue,
  } = state;

  const totalQuestions = questions.length;
  const currentQuestion = questions[currentStep];

  if (!currentQuestion) return null;

  const selectedAnswer = answers[currentQuestion.id];
  const progress =
    totalQuestions > 0 ? ((currentStep + 1) / totalQuestions) * 100 : 0;

  return (
    <OnboardingLayout progress={progress} logout={logout}>
      <OnboardingHeader question={currentQuestion} />

      <OptionsRenderer
        question={currentQuestion}
        selectedAnswer={selectedAnswer}
        open={open}
        setOpen={setOpen}
        handleOptionSelect={handleOptionSelect}
        getOptionLabel={getOptionLabel}
        getOptionValue={getOptionValue}
      />

      <OnboardingFooter
        currentStep={currentStep}
        handleBack={handleBack}
        handleNext={handleNext}
        totalQuestions={totalQuestions}
        handleComplete={handleComplete}
        selectedAnswer={selectedAnswer}
        isSubmitting={isSubmitting}
      />
    </OnboardingLayout>
  );
};

const ProgressBar: React.FC<{ progress: number }> = ({ progress }) => (
  <div className="h-1.5 w-full bg-muted/30 rounded-full overflow-hidden">
    <div
      className="bg-primary h-full transition-all duration-500 ease-out rounded-full shadow-[0_0_10px_rgba(var(--primary),0.5)]"
      style={{ width: `${progress}%` }}
    />
  </div>
);

type OptionsProps = {
  question: Question;
  selectedAnswer: Answer;
  open: boolean;
  setOpen: (v: boolean) => void;
  handleOptionSelect: (opt: Option, id: number, type: string) => void;
  getOptionLabel: (opt: Option) => string;
  getOptionValue: (opt: Option) => string;
};

const OptionsRenderer: React.FC<OptionsProps> = (props) => {
  const { question } = props;

  if (question.question_type === 'dropdown') {
    return <DropdownOptions {...props} />;
  }

  return <ButtonOptions {...props} />;
};

/* ---------------- MAIN ---------------- */

const UserOnboarding: React.FC = () => {
  const state = useUserOnboarding();
  const { logout } = useAuth();

  if (state.isLoadingQuestions) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-foreground">
        <Loader2 className="animate-spin w-10 h-10 text-primary" />
      </div>
    );
  }

  return <UserOnboardingView state={state} logout={logout} />;
};

export default UserOnboarding;
