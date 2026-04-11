/**
 * App.tsx — entry point.
 * Loads fonts, then renders the navigation stack.
 * M5: HomeScreen. M6 fills in ArticleListScreen.
 */

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
import { ActivityIndicator, View } from 'react-native';

import ArticleListScreen from './screens/ArticleListScreen';
import HomeScreen from './screens/HomeScreen';
import { Colors } from './theme/colors';

const Stack = createNativeStackNavigator();

export default function App() {
  // useFonts from @expo-google-fonts/inter v0.4 accepts a name→file map
  const [fontsLoaded] = useFonts({
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    Inter_400Regular,
    Inter_500Medium,
  });

  if (!fontsLoaded) {
    return (
      <View style={{ flex: 1, backgroundColor: Colors.bgBase, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={Colors.accent} />
      </View>
    );
  }

  return (
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
  );
}
