import AVFoundation
import CallKit
import Flutter
import Foundation
import PushKit

enum VoipCallPolicy {
  static func canonicalUUID(_ callId: String) -> UUID? { UUID(uuidString: callId) }
  static func isNewer(_ incoming: Int64, than highest: Int64) -> Bool { incoming > highest }
  static func isExpired(_ expiry: TimeInterval, now: TimeInterval) -> Bool { expiry <= now }
}

/// PushKit and CallKit must exist before Flutter's engine or auth session does.
/// Only opaque call IDs, versions, expiry and generic UI cross this bridge.
final class VoipCallBridge: NSObject, PKPushRegistryDelegate, CXProviderDelegate {
  private struct ReportedCall {
    let version: Int64
    let expiresAt: TimeInterval
    var connected: Bool
    var timer: Timer?
  }

  private let provider: CXProvider
  private var registry: PKPushRegistry?
  private var callChannel: FlutterMethodChannel?
  private var tokenChannel: FlutterMethodChannel?
  private var currentToken: String?
  private var tokenInvalidated = false
  private var calls: [String: ReportedCall] = [:]
  private var audioActive = false
  private let defaults = UserDefaults.standard

  override init() {
    let configuration = CXProviderConfiguration(localizedName: "Astrofrekans")
    configuration.supportsVideo = true
    configuration.maximumCallGroups = 1
    configuration.maximumCallsPerCallGroup = 1
    provider = CXProvider(configuration: configuration)
    super.init()
    provider.setDelegate(self, queue: .main)
  }

  func start() {
    if let id = defaults.string(forKey: "reported_call_id"),
       let uuid = UUID(uuidString: id) {
      let expiry = defaults.double(forKey: "reported_call_expiry")
      let version = Int64(defaults.integer(forKey: "reported_call_version"))
      if expiry > Date().timeIntervalSince1970 && version > 0 {
        var restored = ReportedCall(version: version, expiresAt: expiry, connected: false, timer: nil)
        restored.timer = Timer.scheduledTimer(withTimeInterval: expiry - Date().timeIntervalSince1970, repeats: false) { [weak self] _ in
          self?.endLocal(id: id, reason: .unanswered)
        }
        calls[id] = restored
      } else {
        forgetReported()
        provider.reportCall(with: uuid, endedAt: Date(), reason: .unanswered)
      }
    }
    let registry = PKPushRegistry(queue: .main)
    registry.delegate = self
    registry.desiredPushTypes = [.voIP]
    self.registry = registry
  }

  func attach(messenger: FlutterBinaryMessenger) {
    callChannel = FlutterMethodChannel(name: "astrofrekans/ios_calls", binaryMessenger: messenger)
    callChannel?.setMethodCallHandler { [weak self] call, result in
      guard let self = self else { result(FlutterError(code: "bridge_unavailable", message: nil, details: nil)); return }
      switch call.method {
      case "consumeAction": result(self.consumeAction())
      case "clearPending": self.clearPending(); result(nil)
      case "dismiss":
        if let id = (call.arguments as? [String: Any])?["callId"] as? String {
          self.endLocal(id: id, reason: .remoteEnded)
        }
        result(nil)
      case "markConnected":
        if let id = (call.arguments as? [String: Any])?["callId"] as? String,
           var current = self.calls[id] {
          current.timer?.invalidate()
          current.timer = nil
          current.connected = true
          self.calls[id] = current
        }
        result(nil)
      case "reconcile":
        if let args = call.arguments as? [String: Any],
           let id = args["callId"] as? String,
           let status = args["status"] as? String {
          let terminal = ["ended", "cancelled", "missed", "failed"].contains(status)
          if terminal {
            self.endLocal(id: id, reason: .remoteEnded)
          }
        }
        result(nil)
      case "audioState": result(self.audioActive)
      case "hasCall":
        let id = (call.arguments as? [String: Any])?["callId"] as? String ?? ""
        result(self.calls[id] != nil)
      default: result(FlutterMethodNotImplemented)
      }
    }
    tokenChannel = FlutterMethodChannel(name: "astrofrekans/voip_tokens", binaryMessenger: messenger)
    tokenChannel?.setMethodCallHandler { [weak self] call, result in
      guard let self = self else { result(nil); return }
      switch call.method {
      case "currentToken":
        let token = self.currentToken
        if let token = token {
          result(["token": token, "environment": self.environment])
        } else {
          result(nil)
        }
      case "consumeInvalidation":
        result(self.tokenInvalidated)
        self.tokenInvalidated = false
      default: result(FlutterMethodNotImplemented)
      }
    }
  }

  private var environment: String {
    #if DEBUG
      return "sandbox"
    #else
      return "production"
    #endif
  }

  func pushRegistry(_ registry: PKPushRegistry, didUpdate pushCredentials: PKPushCredentials, for type: PKPushType) {
    guard type == .voIP else { return }
    let token = pushCredentials.token.map { String(format: "%02x", $0) }.joined()
    currentToken = token
    tokenChannel?.invokeMethod("tokenUpdated", arguments: nil)
  }

  func pushRegistry(_ registry: PKPushRegistry, didInvalidatePushTokenFor type: PKPushType) {
    guard type == .voIP else { return }
    currentToken = nil
    tokenInvalidated = true
    tokenChannel?.invokeMethod("tokenInvalidated", arguments: nil)
  }

  func pushRegistry(
    _ registry: PKPushRegistry,
    didReceiveIncomingPushWith payload: PKPushPayload,
    for type: PKPushType,
    completion: @escaping () -> Void
  ) {
    guard type == .voIP else { completion(); return }
    let fields = payload.dictionaryPayload
    let rawId = fields["call_id"] as? String ?? ""
    let parsedUUID = VoipCallPolicy.canonicalUUID(rawId)
    let uuid = parsedUUID ?? UUID(uuidString: "00000000-0000-5000-8000-000000000000")!
    let id = uuid.uuidString.lowercased()
    let version = Int64(fields["event_version"] as? String ?? "") ?? 0
    let expiresAt = TimeInterval(fields["expires_at"] as? String ?? "") ?? 0
    let callType = fields["call_type"] as? String ?? ""
    let valid = fields["event"] as? String == "incoming_call" &&
      parsedUUID != nil && version > 0 &&
      (callType == "audio" || callType == "video")
    let highest = Int64(defaults.integer(forKey: "call_v_\(id)"))
    let duplicate = !valid || !VoipCallPolicy.isNewer(version, than: highest)
    if valid && !duplicate { defaults.set(version, forKey: "call_v_\(id)") }

    let update = CXCallUpdate()
    update.remoteHandle = CXHandle(type: .generic, value: "Astrofrekans")
    update.localizedCallerName = "Astrofrekans"
    update.hasVideo = callType == "video"
    // Every VoIP push is reported promptly, including a stale/duplicate one.
    // CallKit may reject reuse of an already-present UUID; no second UUID/UI
    // is invented in that case.
    provider.reportNewIncomingCall(with: uuid, update: update) { [weak self] error in
      DispatchQueue.main.async {
        guard let self = self else { completion(); return }
        let expired = VoipCallPolicy.isExpired(expiresAt, now: Date().timeIntervalSince1970)
        if error == nil && valid && !duplicate && !expired {
          var reported = ReportedCall(version: version, expiresAt: expiresAt, connected: false, timer: nil)
          reported.timer = Timer.scheduledTimer(withTimeInterval: max(0.01, expiresAt - Date().timeIntervalSince1970), repeats: false) { [weak self] _ in
            self?.endLocal(id: id, reason: .unanswered)
          }
          self.calls[id] = reported
          self.defaults.set(id, forKey: "reported_call_id")
          self.defaults.set(version, forKey: "reported_call_version")
          self.defaults.set(expiresAt, forKey: "reported_call_expiry")
          self.callChannel?.invokeMethod("incoming", arguments: ["callId": id])
        } else if self.calls[id] == nil {
          self.provider.reportCall(with: uuid, endedAt: Date(), reason: expired ? .unanswered : .remoteEnded)
        }
        completion() // Apple sample completes after CallKit's report callback.
      }
    }
  }

  private func endLocal(id: String, reason: CXCallEndedReason) {
    guard let uuid = UUID(uuidString: id) else { return }
    guard calls[id] != nil else { return }
    calls[id]?.timer?.invalidate()
    calls.removeValue(forKey: id)
    forgetReported()
    provider.reportCall(with: uuid, endedAt: Date(), reason: reason)
  }

  private func forgetReported() {
    for key in ["reported_call_id", "reported_call_version", "reported_call_expiry"] {
      defaults.removeObject(forKey: key)
    }
  }

  private func saveAction(id: String, action: String) {
    guard let call = calls[id] else { return }
    defaults.set(id, forKey: "pending_call_id")
    defaults.set(action, forKey: "pending_call_action")
    defaults.set(call.version, forKey: "pending_call_version")
    defaults.set(call.connected ? Date().timeIntervalSince1970 + 60 : call.expiresAt,
                 forKey: "pending_call_expiry")
    callChannel?.invokeMethod("action", arguments: nil)
  }

  private func consumeAction() -> [String: Any]? {
    let id = defaults.string(forKey: "pending_call_id")
    let action = defaults.string(forKey: "pending_call_action")
    let version = Int64(defaults.integer(forKey: "pending_call_version"))
    let expiry = defaults.double(forKey: "pending_call_expiry")
    clearPending()
    guard let id = id, let action = action,
      expiry > Date().timeIntervalSince1970,
      version > 0,
      version == Int64(defaults.integer(forKey: "call_v_\(id)")) else { return nil }
    return ["callId": id, "action": action,
      "eventVersion": version, "expiresAt": Int64(expiry)]
  }

  private func clearPending() {
    for key in ["pending_call_id", "pending_call_action", "pending_call_version", "pending_call_expiry"] {
      defaults.removeObject(forKey: key)
    }
  }

  func providerDidReset(_ provider: CXProvider) {
    for (_, call) in calls { call.timer?.invalidate() }
    calls.removeAll()
    forgetReported()
    clearPending()
  }

  func provider(_ provider: CXProvider, perform action: CXAnswerCallAction) {
    let id = action.callUUID.uuidString.lowercased()
    guard let call = calls[id], call.expiresAt > Date().timeIntervalSince1970 else {
      action.fail()
      endLocal(id: id, reason: .unanswered)
      return
    }
    saveAction(id: id, action: "answer")
    action.fulfill() // CallKit may now activate audio; Flutter authorizes/joins next.
  }

  func provider(_ provider: CXProvider, perform action: CXEndCallAction) {
    let id = action.callUUID.uuidString.lowercased()
    saveAction(id: id, action: calls[id]?.connected == true ? "end" : "decline")
    calls[id]?.timer?.invalidate()
    calls.removeValue(forKey: id)
    forgetReported()
    action.fulfill()
  }

  func provider(_ provider: CXProvider, didActivate audioSession: AVAudioSession) {
    audioActive = true
    callChannel?.invokeMethod("audioActivated", arguments: nil)
  }

  func provider(_ provider: CXProvider, didDeactivate audioSession: AVAudioSession) {
    audioActive = false
    callChannel?.invokeMethod("audioDeactivated", arguments: nil)
  }
}
