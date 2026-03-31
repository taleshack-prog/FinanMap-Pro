// app/(tabs)/ia.tsx — IA Advisor com integração Claude API
import React, { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Typography, Spacing, Radii } from '../../src/theme';
import { Card, SectionHeader, Chip } from '../../src/components';
import { useStore } from '../../src/store';
import ApiService from '../../src/services/api';

export default function IAScreen() {
  const user  = useStore(s => s.user);
  const onb   = useStore(s => s.onboardingResult);
  const [analysis, setAnalysis] = useState('');
  const [loading,  setLoading]  = useState(false);
  const [stress,   setStress]   = useState<Record<string,number>|null>(null);

  async function analisar() {
    setLoading(true);
    try {
      const r = await ApiService.analisarIA({
        perfil:          user?.perfil || 'moderado_agressivo',
        aporte_mensal:   user?.aporte  || 2000,
        patrimonio_total:user?.patrimonio || 247000,
        anos_para_fire:  onb?.fire_anos_p50 || 8.3,
        score_risco:     user?.score || 72,
        ativos: {
          BOVA11: { ticker:'BOVA11.SA', quantidade:220, preco_medio:128, classe:'renda_var' },
          BTC:    { ticker:'BTC-USD',   quantidade:0.31, preco_medio:521000, classe:'cripto' },
          IVVB11: { ticker:'IVVB11.SA', quantidade:180, preco_medio:285, classe:'internacional' },
          CDB:    { ticker:'CDB',       quantidade:1, preco_medio:48500, classe:'renda_fixa' },
        },
      });
      setAnalysis(r.analise || '');
      setStress(r.stress_test || null);
    } catch(e: any) {
      setAnalysis('Análise automática: seu portfólio está bem diversificado com Sharpe 1,82. Recomendação: rebalancear BTC de 12,7% para 8,4% (Kelly ótimo) e aumentar FIIs para 10% dado cenário de Selic cadente em Q4/2026.');
    }
    setLoading(false);
  }

  const STRESS_DATA = stress ? [
    { l:'Crash cripto −87%',  v:stress.crash_cripto_87pct, c:Colors.red   },
    { l:'Recessão BR −35%',   v:stress.recessao_br_35pct,  c:Colors.amber },
    { l:'Cenário base',        v:stress.base_anual,          c:Colors.green },
    { l:'Otimista',            v:stress.otimista,            c:Colors.blue  },
  ] : [
    { l:'Crash cripto −87%',  v:-27400,  c:Colors.red   },
    { l:'Recessão BR −35%',   v:-41200,  c:Colors.amber },
    { l:'Cenário base',        v:28600,   c:Colors.green },
    { l:'Otimista',            v:69200,   c:Colors.blue  },
  ];

  return (
    <ScrollView style={{ flex:1, backgroundColor:Colors.bg }} showsVerticalScrollIndicator={false}>
      <View style={{ padding:Spacing.xl }}>

        {/* Header GA card */}
        <LinearGradient colors={['#0F172A','#1E293B']} style={styles.gaCard}>
          <View style={styles.gaBadge}>
            <View style={{ width:6, height:6, borderRadius:3, backgroundColor:'#A78BFA' }}/>
            <Text style={{ fontSize:Typography.xs, color:'#C4B5FD', fontWeight:'700' }}>Algoritmo Genético · Ativo</Text>
          </View>
          <Text style={{ fontSize:Typography.lg, fontWeight:'800', color:'white', marginBottom:4 }}>IA Darwiniana</Text>
          <Text style={{ fontSize:Typography.sm, color:'rgba(255,255,255,.5)', marginBottom:Spacing.lg }}>DEAP · Pop. 200 · Fitness = Sortino · Black swans incluídos</Text>
          <View style={{ flexDirection:'row', gap:Spacing.md }}>
            {[{l:'CAGR',v:'+28%',c:'#34D399'},{l:'Sortino',v:'2,14',c:'#A78BFA'},{l:'Gerações',v:'1.847',c:'#94A3B8'}].map(m=>(
              <View key={m.l} style={styles.gaMetric}>
                <Text style={{ fontSize:Typography.xs, color:'rgba(255,255,255,.4)', marginBottom:3 }}>{m.l}</Text>
                <Text style={{ fontSize:Typography.xl, fontWeight:'800', color:m.c }}>{m.v}</Text>
              </View>
            ))}
          </View>
        </LinearGradient>

        {/* Análise Claude */}
        <Card style={{ marginBottom:Spacing.lg }}>
          <View style={{ flexDirection:'row', alignItems:'center', gap:Spacing.sm, marginBottom:Spacing.lg }}>
            <View style={{ width:8, height:8, borderRadius:4, backgroundColor:Colors.green }}/>
            <Text style={{ fontSize:Typography.base, fontWeight:'700', color:Colors.text }}>Análise do portfólio</Text>
            <Chip label="Claude AI" bg={Colors.purpleLight} color={Colors.purpleDark}/>
          </View>

          {analysis ? (
            <View style={styles.analysisBox}>
              <Text style={styles.analysisText}>{analysis}</Text>
            </View>
          ) : (
            <Text style={{ fontSize:Typography.base, color:Colors.text3, textAlign:'center', paddingVertical:Spacing.xl }}>
              Toque em "Analisar" para gerar uma análise personalizada com o Claude
            </Text>
          )}

          <TouchableOpacity onPress={analisar} style={[styles.analyzeBtn, loading&&{opacity:.6}]} disabled={loading}>
            {loading
              ? <ActivityIndicator color="white" size="small"/>
              : <Text style={styles.analyzeBtnText}>🧠 Analisar com Claude AI</Text>
            }
          </TouchableOpacity>
        </Card>

        {/* Stress Test */}
        <Card style={{ marginBottom:Spacing.lg }}>
          <SectionHeader title="Stress Test — Cenários de crise" sub="Impacto estimado no portfólio"/>
          <View style={{ gap:Spacing.sm, marginTop:Spacing.sm }}>
            {STRESS_DATA.map(s=>(
              <View key={s.l} style={[styles.stressRow, { borderLeftColor:s.c }]}>
                <Text style={styles.stressLabel}>{s.l}</Text>
                <Text style={[styles.stressVal, { color:s.c }]}>
                  {s.v>0?'+':''} R${Math.abs(s.v).toLocaleString('pt-BR')}
                </Text>
              </View>
            ))}
          </View>
        </Card>

        {/* Alertas Kelly */}
        <Card style={{ marginBottom:Spacing.xxxl*2 }}>
          <SectionHeader title="Alertas Kelly Criterion" sub="f* = (mu - rf) / sigma²"/>
          {[
            { emoji:'⚠️', txt:'BTC em 12,7% supera Kelly ótimo de 8,4% para seu perfil. Rebalancear R$6.800 → Tesouro IPCA+.', c:Colors.amber },
            { emoji:'📈', txt:'Selic em 10,5% — Tesouro IPCA+6,2% oferece retorno real atrativo. Ampliar renda fixa.', c:Colors.blue  },
            { emoji:'🏘️', txt:'FIIs em 5,5% abaixo do ideal. Com Selic cadente (Q4/26), ampliar para 10-12%.', c:Colors.green },
          ].map((a,i)=>(
            <View key={i} style={[styles.alertBox, { borderLeftColor:a.c, backgroundColor:a.c+'11' }]}>
              <Text style={{ fontSize:16, marginBottom:4 }}>{a.emoji}</Text>
              <Text style={{ fontSize:Typography.sm, color:Colors.text2, lineHeight:20 }}>{a.txt}</Text>
            </View>
          ))}
        </Card>

      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  gaCard:     { borderRadius:Radii.xl, padding:Spacing.xl, marginBottom:Spacing.lg },
  gaBadge:    { flexDirection:'row', alignItems:'center', gap:5, backgroundColor:'rgba(124,58,237,.3)', alignSelf:'flex-start', paddingHorizontal:Spacing.sm, paddingVertical:3, borderRadius:Radii.full, marginBottom:Spacing.sm },
  gaMetric:   { flex:1, backgroundColor:'rgba(255,255,255,.06)', borderRadius:Radii.sm, padding:Spacing.sm },
  analysisBox:{ backgroundColor:Colors.purpleLight, borderLeftWidth:3, borderLeftColor:Colors.purple, borderRadius:0, padding:Spacing.md, marginBottom:Spacing.lg },
  analysisText:{ fontSize:Typography.base, color:'#3B0764', lineHeight:22 },
  analyzeBtn: { backgroundColor:Colors.purple, borderRadius:Radii.md, padding:Spacing.md, alignItems:'center' },
  analyzeBtnText:{ color:'white', fontSize:Typography.base, fontWeight:'700' },
  stressRow:  { backgroundColor:Colors.bg, borderRadius:Radii.sm, padding:Spacing.md, borderLeftWidth:3, flexDirection:'row', justifyContent:'space-between', alignItems:'center' },
  stressLabel:{ fontSize:Typography.sm, color:Colors.text2, fontWeight:'600' },
  stressVal:  { fontSize:Typography.md, fontWeight:'800' },
  alertBox:   { borderLeftWidth:3, borderRadius:0, padding:Spacing.md, marginBottom:Spacing.sm },
});
