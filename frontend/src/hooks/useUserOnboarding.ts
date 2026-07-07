import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { OnboardingApi, type Question, type AnswerCreate } from '@/api/auth';
import { useAuth } from '@/context/AuthContext';

interface UserAnswer {
  value: string;
  option_id: number | null;
}

interface OnboardingOption {
  label?: string;
  name?: string;
  text?: string;
  value?: string;
  id?: number | string;
  code?: string;
  option_id?: number | string;
}

const useOnboardingQuestions = (checkAuth: () => void) => {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);

  const fetchQuestions = useCallback(async () => {
    setIsLoadingQuestions(true);
    try {
      const res = await OnboardingApi.fetchQuestions();

      setQuestions(res);
    } catch (err) {
      console.error('Failed to fetch questions:', err);
    } finally {
      setIsLoadingQuestions(false);
    }
  }, []);

  useEffect(() => {
    fetchQuestions();
    checkAuth();
  }, [fetchQuestions, checkAuth]);

  return { questions, isLoadingQuestions };
};

const useOnboardingHelpers = () => {
  const getOptionLabel = (option: string | OnboardingOption) => typeof option === 'string'
    ? option
    : option.label || option.name || option.text || String(option);

  const getOptionValue = (option: string | OnboardingOption) => typeof option === 'string'
    ? option
    : String(
      option.value || option.id || option.code || getOptionLabel(option),
    );

  const getOptionId = (option: string | OnboardingOption) => {
    if (typeof option === 'string') return null;
    const id = option.id || option.option_id;

    return id !== undefined ? Number(id) : null;
  };

  return { getOptionLabel, getOptionValue, getOptionId };
};

const formatAnswers = (
  answers: Record<number, UserAnswer>,
): AnswerCreate[] => Object.entries(answers).map(([qId, data]) => ({
  question_id: Number(qId),
  option_id: data.option_id,
  answer_value: data.value,
}));

const useOnboardingSubmit = (
  navigate: ReturnType<typeof useNavigate>,
  checkAuth: () => void,
) => {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (answers: Record<number, UserAnswer>) => {
    setIsSubmitting(true);

    try {
      const formatted = formatAnswers(answers);

      await OnboardingApi.submitOnboarding(formatted);
      await checkAuth();
      navigate('/dashboard');
    } catch (err) {
      console.error('Failed to submit onboarding:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return { isSubmitting, submit };
};

const useOnboardingNavigation = (
  currentStep: number,
  setCurrentStep: React.Dispatch<React.SetStateAction<number>>,
) => {
  const handleNext = (total: number, onComplete: () => void) => {
    if (currentStep < total - 1) {
      setCurrentStep((p) => p + 1);
    } else {
      onComplete();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((p) => p - 1);
    }
  };

  return { handleNext, handleBack };
};

const useOptionSelect = (
  setAnswers: React.Dispatch<React.SetStateAction<Record<number, UserAnswer>>>,
  setOpen: (v: boolean) => void,
) => {
  const { getOptionValue, getOptionId } = useOnboardingHelpers();

  const handleOptionSelect = (
    option: string | OnboardingOption,
    questionId: number,
    type: string,
  ) => {
    const value = getOptionValue(option);
    const option_id = getOptionId(option);

    setAnswers((prev) => ({
      ...prev,
      [questionId]: { value, option_id },
    }));

    if (type === 'dropdown') setOpen(false);
  };

  return { handleOptionSelect };
};

const useOnboardingActions = (
  answers: Record<number, UserAnswer>,
  setAnswers: React.Dispatch<React.SetStateAction<Record<number, UserAnswer>>>,
  currentStep: number,
  setCurrentStep: React.Dispatch<React.SetStateAction<number>>,
  setOpen: (v: boolean) => void,
  navigate: ReturnType<typeof useNavigate>,
  checkAuth: () => void,
) => {
  const { isSubmitting, submit } = useOnboardingSubmit(navigate, checkAuth);

  const { handleNext, handleBack } = useOnboardingNavigation(
    currentStep,
    setCurrentStep,
  );

  const { handleOptionSelect } = useOptionSelect(setAnswers, setOpen);

  const handleComplete = () => submit(answers);

  return {
    isSubmitting,
    handleOptionSelect,
    handleNext,
    handleBack,
    handleComplete,
  };
};

export const useUserOnboarding = () => {
  const navigate = useNavigate();
  const { checkAuth } = useAuth();

  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<number, UserAnswer>>({});
  const [open, setOpen] = useState(false);

  const { questions, isLoadingQuestions } = useOnboardingQuestions(checkAuth);

  const {
    isSubmitting,
    handleOptionSelect,
    handleNext,
    handleBack,
    handleComplete,
  } = useOnboardingActions(
    answers,
    setAnswers,
    currentStep,
    setCurrentStep,
    setOpen,
    navigate,
    checkAuth,
  );

  const { getOptionLabel, getOptionValue } = useOnboardingHelpers();

  return {
    currentStep,
    answers,
    open,
    setOpen,
    isLoadingQuestions,
    isSubmitting,
    questions,
    handleOptionSelect,
    handleNext,
    handleBack,
    handleComplete,
    getOptionLabel,
    getOptionValue,
  };
};
