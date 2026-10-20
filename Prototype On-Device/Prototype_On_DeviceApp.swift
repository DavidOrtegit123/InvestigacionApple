//
//  Prototype_On_DeviceApp.swift
//  Prototype On-Device
//
//  Created by David Ortega Muzquiz on 12/08/26.
//

import SwiftUI

@main
struct Prototype_On_DeviceApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}

struct RootView: View {
    @StateObject private var memoryStore = StudentMemoryStore()

    var body: some View {
        if memoryStore.memory.name.isEmpty {
            OnboardingView(memoryStore: memoryStore)
        } else {
            ContentView(memoryStore: memoryStore)
        }
    }
}
