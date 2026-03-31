// app/(tabs)/_layout.tsx — Bottom tab navigator
import { Tabs } from 'expo-router';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Typography } from '../../src/theme';

function TabIcon({ name, focused, emoji }: { name:string; focused:boolean; emoji:string }) {
  return (
    <View style={[styles.tabIcon, focused && styles.tabIconActive]}>
      <Text style={{ fontSize: 18 }}>{emoji}</Text>
      {focused && <View style={styles.tabDot}/>}
    </View>
  );
}

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{
      headerShown:      false,
      tabBarStyle:      styles.tabBar,
      tabBarLabelStyle: styles.tabLabel,
      tabBarActiveTintColor:   Colors.purple,
      tabBarInactiveTintColor: Colors.text3,
    }}>
      <Tabs.Screen
        name="dashboard"
        options={{ title:'Início',
          tabBarIcon: ({ focused }) => <TabIcon name="dashboard" focused={focused} emoji="🏠"/>
        }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{ title:'Portfólio',
          tabBarIcon: ({ focused }) => <TabIcon name="portfolio" focused={focused} emoji="📊"/>
        }}
      />
      <Tabs.Screen
        name="robots"
        options={{ title:'Robôs',
          tabBarIcon: ({ focused }) => (
            <View>
              <TabIcon name="robots" focused={focused} emoji="🤖"/>
              {!focused && <View style={styles.newBadge}><Text style={styles.newText}>NEW</Text></View>}
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="fire"
        options={{ title:'FIRE',
          tabBarIcon: ({ focused }) => <TabIcon name="fire" focused={focused} emoji="🔥"/>
        }}
      />
      <Tabs.Screen
        name="ia"
        options={{ title:'IA',
          tabBarIcon: ({ focused }) => <TabIcon name="ia" focused={focused} emoji="🧬"/>
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: Colors.surface,
    borderTopWidth:  1,
    borderTopColor:  Colors.border,
    height:          72,
    paddingBottom:   12,
    paddingTop:       6,
  },
  tabLabel: {
    fontSize:   Typography.xs,
    fontWeight: Typography.semibold,
    marginTop:  2,
  },
  tabIcon: {
    alignItems:     'center',
    justifyContent: 'center',
    width:          40,
    height:         32,
    borderRadius:   12,
  },
  tabIconActive: {
    backgroundColor: Colors.purpleLight,
  },
  tabDot: {
    position:        'absolute',
    bottom:          -4,
    width:           4,
    height:          4,
    borderRadius:    2,
    backgroundColor: Colors.purple,
  },
  newBadge: {
    position:        'absolute',
    top:             -2,
    right:           -4,
    backgroundColor: Colors.amber,
    borderRadius:    8,
    paddingHorizontal: 3,
    paddingVertical:   1,
  },
  newText: {
    fontSize:   7,
    fontWeight: '800',
    color:      'white',
  },
});
