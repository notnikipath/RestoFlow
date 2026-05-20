import React from "react";
import { SafeAreaView, Text, View } from "react-native";

export default function App() {
  return (
    <SafeAreaView style={{ flex: 1, padding: 20, backgroundColor: "#eff9f7" }}>
      <Text style={{ fontSize: 28, fontWeight: "700", marginBottom: 12 }}>RestoFlow Kitchen</Text>
      <View style={{ padding: 14, borderRadius: 12, backgroundColor: "#c9f3eb" }}>
        <Text>Kitchen board:</Text>
        <Text>- Queued tickets</Text>
        <Text>- Preparing</Text>
        <Text>- Ready for pickup</Text>
        <Text>- Delivered</Text>
      </View>
    </SafeAreaView>
  );
}
