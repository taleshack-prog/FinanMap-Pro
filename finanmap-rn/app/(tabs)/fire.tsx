// app/(tabs)/fire.tsx — FIRE Tracker interativo
import React, { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet } from 'react-native';
import { Colors, Typography, Spacing, Radii } from '../../src/theme';
import { Card, SectionHeader, ProgressBar, MetricCard } from '../../src/components';
import { useStore } from '../../src/store';
import ApiService from '../../src/services/api';

export default function FireScreen() {
  const user = useStore(s => s.user);
  const setFire = useStore(s => s.setFireResult);
  const fire    = useStore(s => s.fireResult);

  const [desp,    setDesp]    = useState(user?.despesas  || 5000);
  const [aporte,  setAporte]  = useState(user?.aporte    || 2000);
  const [rent,    setRent]    = useState(12);
  const [pat,     setPat]     = useState(user?.patrimonio|| 50000);
  const [loading, setLoading] = useState(false);

  const meta     = desp * 25 * 12;
  const progress = Math.min(100, Math.round(pat / meta * 100));
  const anos_p50 = fire?.monte_carlo?.anos_p50 || fire?.anos_para_fire || 8.3;
  const prob     = fire?.monte_carlo?.prob_sucesso_pct || 87;
  const renda    = Math.round(meta * 0.04 / 12);

  async function recalcular() {
    setLoading(true);
    try {
      const r = await ApiService.calcularFire({ aporte_mensal:aporte, despesas_mensais:desp, patrimonio_atual:pat, risco: rent/100 });
      setFire(r);
    } catch {}
    setLoading(false);
  }

  const SLIDERS = [
    { label:'Despesas mensais', val:desp,   set:setDesp,   min:1000,  max:15000, step:500,   fmt:(v:number)=>'R$'+v.toLocaleString('pt-BR') },
    { label:'Aporte mensal',    val:aporte, set:setAporte, min:500,   max:20000, step:500,   fmt:(v:number)=>'R$'+v.toLocaleString('pt-BR') },
    { label:'Rentabilidade',    val:rent,   set:setRent,   min:4,     max:25,    step:0.5,   fmt:(v:number)=>v.toFixed(1)+'%' },
    { label:'Patrimônio atual', val:pat,    set:setPat,    min:0,     max:500000,step:5000,  fmt:(v:number)=>'R$'+Math.round(v/1000)+'k' },
  ];

  return (
    <ScrollView style={{ flex:1, backgroundColor:Colors.bg }} showsVerticalScrollIndicator={false}>
      <View style={{ padding:Spacing.xl }}>

        {/* Resultado principal */}
        <Card style={{ marginBottom:Spacing.lg, alignItems:'center', paddingVertical:Spacing.xxl }}>
          <Text style={{ fontSize:Typography.sm, color:Colors.text3, marginBottom:Spacing.xs }}>Você atinge FIRE em</Text>
          <Text style={{ fontSize:60, fontWeight:'800', color:Colors.purple, lineHeight:68 }}>{anos_p50.toFixed(1)}</Text>
          <Text style={{ fontSize:Typography.xl, fontWeight:'700', color:Colors.text, marginBottom:Spacing.sm }}>anos</Text>
          <Text style={{ fontSize:Typography.base, color:Colors.text2 }}>com <Text style={{ color:Colors.green, fontWeight:'800' }}>{prob.toFixed(0)}%</Text> de probabilidade</Text>
        </Card>

        {/* Métricas */}
        <View style={{ flexDirection:'row', gap:Spacing.sm, marginBottom:Spacing.lg }}>
          <MetricCard label="Meta (25×)"  value={'R$'+Math.round(meta/1000)+'k'}        accent={Colors.amber}  style={{flex:1}}/>
          <MetricCard label="Cenário p90" value={(anos_p50*1.45).toFixed(1)+'a'}         accent={Colors.red}    style={{flex:1}}/>
          <MetricCard label="Renda FIRE"  value={'R$'+renda.toLocaleString('pt-BR')+'/m'} accent={Colors.green} style={{flex:1}}/>
        </View>

        {/* Progresso */}
        <Card style={{ marginBottom:Spacing.lg }}>
          <View style={{ flexDirection:'row', justifyContent:'space-between', marginBottom:Spacing.xs }}>
            <Text style={{ fontSize:Typography.sm, color:Colors.text2, fontWeight:'600' }}>Progresso</Text>
            <Text style={{ fontSize:Typography.sm, fontWeight:'800', color:Colors.purple }}>{progress}%</Text>
          </View>
          <ProgressBar progress={progress} />
          <View style={{ flexDirection:'row', justifyContent:'space-between', marginTop:Spacing.xs }}>
            <Text style={{ fontSize:Typography.xs, color:Colors.text3 }}>R${Math.round(pat/1000)}k atual</Text>
            <Text style={{ fontSize:Typography.xs, color:Colors.text3 }}>Meta: R${Math.round(meta/1000)}k</Text>
          </View>
        </Card>

        {/* Sliders */}
        <Card style={{ marginBottom:Spacing.lg }}>
          <SectionHeader title="Parâmetros" sub="Ajuste e veja o impacto em tempo real"/>
          {SLIDERS.map(sl=>(
            <View key={sl.label} style={{ marginBottom:Spacing.md }}>
              <View style={{ flexDirection:'row', justifyContent:'space-between', marginBottom:Spacing.xs }}>
                <Text style={{ fontSize:Typography.sm, color:Colors.text2, fontWeight:'600' }}>{sl.label}</Text>
                <Text style={{ fontSize:Typography.sm, fontWeight:'800', color:Colors.purple }}>{sl.fmt(sl.val)}</Text>
              </View>
              <View style={{ flexDirection:'row', flexWrap:'wrap', gap:6 }}>
                {Array.from({length:8},(_,i)=>Math.round(sl.min + (sl.max-sl.min)/7*i)).map(v=>(
                  <TouchableOpacity key={v} onPress={()=>{ sl.set(v); }}
                    style={[{ paddingHorizontal:8, paddingVertical:4, borderRadius:Radii.full, borderWidth:1,
                      borderColor: Math.abs(sl.val-v)<sl.step*2?Colors.purple:Colors.border,
                      backgroundColor: Math.abs(sl.val-v)<sl.step*2?Colors.purpleLight:Colors.bg,
                    }]}>
                    <Text style={{ fontSize:Typography.xs, color: Math.abs(sl.val-v)<sl.step*2?Colors.purple:Colors.text2 }}>{sl.fmt(v)}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ))}
          <TouchableOpacity onPress={recalcular} style={[styles.recalcBtn, loading&&{opacity:.6}]} disabled={loading}>
            <Text style={styles.recalcText}>{loading?'Calculando 10k sims...':'🎲 Recalcular Monte Carlo'}</Text>
          </TouchableOpacity>
        </Card>

      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  recalcBtn:  { backgroundColor:Colors.purple, borderRadius:Radii.md, padding:Spacing.md, alignItems:'center', marginTop:Spacing.sm },
  recalcText: { color:'white', fontSize:Typography.base, fontWeight:'700' },
});
