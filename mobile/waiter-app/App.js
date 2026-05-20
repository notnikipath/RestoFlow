import React from "react";
import { SafeAreaView, Text, View } from "react-native";

export default function App() {
  return (
    <SafeAreaView style={{ flex: 1, padding: 20, backgroundColor: "#fff7ef" }}>
      <Text style={{ fontSize: 28, fontWeight: "700", marginBottom: 12 }}>RestoFlow Waiter</Text>
      <View style={{ padding: 14, borderRadius: 12, backgroundColor: "#ffe2c4" }}>
        <Text>Quick actions:</Text>
        <Text>- Open table</Text>
        <Text>- Add dishes</Text>
        <Text>- Send order to kitchen</Text>
        <Text>- Split bill</Text>
      </View>
    </SafeAreaView>
  );
}
