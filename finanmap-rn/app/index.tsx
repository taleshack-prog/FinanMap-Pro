// app/index.tsx — redireciona para onboarding ou app
import { Redirect } from 'expo-router';
import { useStore } from '../src/store';

export default function Index() {
  const user = useStore(s => s.user);
  if (user?.onboardingDone) return <Redirect href="/(tabs)/dashboard" />;
  return <Redirect href="/onboarding" />;
}
