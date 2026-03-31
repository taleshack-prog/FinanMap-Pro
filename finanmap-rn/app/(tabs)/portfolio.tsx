// app/(tabs)/portfolio.tsx
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { Colors, Typography, Spacing } from '../../src/theme';
import { Card, SectionHeader, MetricCard } from '../../src/components';
import { useStore } from '../../src/store';

const ASSETS = [
  { s:'B', n:'BOVA11',        t:'ETF B3',     qtd:'220',  p:'R$128,40', total:28248, ret:'+14,2%', pos:true,  pct:11.4, c:'#7C3AED' },
  { s:'T', n:'Tesouro IPCA+', t:'Renda Fixa',  qtd:'—',   p:'IPCA+6,2%',total:74000, ret:'+18,8%', pos:true, pct:29.9, c:'#2563EB' },
  { s:'₿', n:'Bitcoin',       t:'Cripto',     qtd:'0,31', p:'R$521k',   total:31500, ret:'+82,4%', pos:true,  pct:12.7, c:'#D97706' },
  { s:'I', n:'IVVB11',        t:'ETF S&P500', qtd:'180',  p:'R$284,90', total:51282, ret:'+22,1%', pos:true,  pct:20.7, c:'#059669' },
  { s:'H', n:'HGLG11',        t:'FII',        qtd:'95',   p:'R$143,20', total:13604, ret:'−2,8%',  pos:false, pct:5.5,  c:'#DC2626' },
  { s:'C', n:'CDB 115% CDI',  t:'Renda Fixa', qtd:'—',    p:'115% CDI', total:48500, ret:'+12,1%', pos:true,  pct:19.6, c:'#7C3AED' },
];

export default function PortfolioScreen() {
  const user = useStore(s => s.user);
  const pat  = user?.patrimonio || 247000;
  return (
    <ScrollView style={{ flex:1, backgroundColor:Colors.bg }} showsVerticalScrollIndicator={false}>
      <View style={styles.metrics}>
        <MetricCard label="Total atual"    value={'R$'+Math.round(pat/1000)+'k'}            accent={Colors.purple} style={{flex:1}}/>
        <MetricCard label="Rentab. 12m"   value="18,4%"                                     accent={Colors.green}  style={{flex:1}}/>
        <MetricCard label="Dividendos 12m" value="R$8.420"                                  accent={Colors.amber}  style={{flex:1}}/>
      </View>
      <View style={{ paddingHorizontal:Spacing.xl }}>
        <Card>
          <SectionHeader title="Carteira" sub="Ativos em carteira · dados ao vivo"/>
          {ASSETS.map(a=>(
            <View key={a.n} style={styles.assetRow}>
              <View style={[styles.assetIcon, { backgroundColor:a.c+'22' }]}>
                <Text style={{ fontSize:12, fontWeight:'800', color:a.c }}>{a.s}</Text>
              </View>
              <View style={{ flex:1 }}>
                <Text style={styles.assetName}>{a.n}</Text>
                <Text style={styles.assetType}>{a.t}</Text>
              </View>
              <View style={{ alignItems:'flex-end' }}>
                <Text style={styles.assetTotal}>R${a.total.toLocaleString('pt-BR')}</Text>
                <Text style={[styles.assetRet, { color:a.pos?Colors.green:Colors.red }]}>{a.ret}</Text>
              </View>
            </View>
          ))}
        </Card>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  metrics:   { flexDirection:'row', gap:Spacing.sm, padding:Spacing.xl, paddingBottom:Spacing.md },
  assetRow:  { flexDirection:'row', alignItems:'center', gap:Spacing.md, paddingVertical:Spacing.sm, borderBottomWidth:1, borderColor:Colors.bg },
  assetIcon: { width:36, height:36, borderRadius:10, alignItems:'center', justifyContent:'center' },
  assetName: { fontSize:Typography.sm, fontWeight:'700', color:Colors.text },
  assetType: { fontSize:Typography.xs, color:Colors.text3 },
  assetTotal:{ fontSize:Typography.sm, fontWeight:'700', color:Colors.text },
  assetRet:  { fontSize:Typography.xs, fontWeight:'700' },
});


// ─────────────────────────────────────────────────────────────────────────────
// app/(tabs)/fire.tsx
export { default as FireScreen } from '../../src/screens/DashboardScreen'; // placeholder

// app/(tabs)/ia.tsx — IA Advisor placeholder
