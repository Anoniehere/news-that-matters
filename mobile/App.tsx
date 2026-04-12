/**
 * App.tsx — entry point.
 * Loads fonts, then renders the navigation stack.
 */

import { enableScreens } from 'react-native-screens';
enableScreens();

import {
  Inter_400Regular,
  Inter_500Medium,
  useFonts,
} from '@expo-google-fonts/inter';
import {
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
} from '@expo-google-fonts/plus-jakarta-sans';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { ActivityIndicator, Text, View } from 'react-native';

import ArticleListScreen from './screens/ArticleListScreen';
import HomeScreen from './screens/HomeScreen';
import { Colors } from './theme/colors';

const Stack = createNativeStackNavigator();

// ── Visible error boundary — surfaces crashes in the UI instead of blank screen ──
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <View style={{ flex: 1, backgroundColor: '#09090B', padding: 24, justifyContent: 'center' }}>
          <Text style={{ color: '#F87171', fontSize: 16, marginBottom: 8 }}>💥 Render error</Text>
          <Text style={{ color: '#A1A1AA', fontSize: 12, fontFamily: 'monospace' }}>
            {String(this.state.error)}
          </Text>
        </View>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  // fontsError → proceed with system fonts rather than hanging on a blank screen
  const [fontsLoaded, fontsError] = useFonts({
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    Inter_400Regular,
    Inter_500Medium,
  });

  if (!fontsLoaded && !fontsError) {
    return (
      <View style={{ flex: 1, backgroundColor: Colors.bgBase, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={Colors.accent} />
        <Text style={{ color: Colors.textMuted, marginTop: 12, fontSize: 13 }}>
          Loading fonts…
        </Text>
      </View>
    );
  }

  return (
    <ErrorBoundary>
      <NavigationContainer>
        <StatusBar style="light" />
        <Stack.Navigator
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: Colors.bgBase },
            animation: 'slide_from_right',
          }}
        >
          <Stack.Screen name="Home"        component={HomeScreen} />
          <Stack.Screen name="ArticleList" component={ArticleListScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </ErrorBoundary>
  );
}
