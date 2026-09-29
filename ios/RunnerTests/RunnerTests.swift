import Flutter
import UIKit
import XCTest
@testable import Runner

class RunnerTests: XCTestCase {

  func testDeterministicCallKitUUID() {
    let id = "11111111-1111-4111-8111-111111111111"
    XCTAssertEqual(VoipCallPolicy.canonicalUUID(id), VoipCallPolicy.canonicalUUID(id))
    XCTAssertNil(VoipCallPolicy.canonicalUUID("not-a-call-id"))
  }

  func testDuplicateOlderNewerAndExpiry() {
    XCTAssertFalse(VoipCallPolicy.isNewer(100, than: 100))
    XCTAssertFalse(VoipCallPolicy.isNewer(99, than: 100))
    XCTAssertTrue(VoipCallPolicy.isNewer(101, than: 100))
    XCTAssertTrue(VoipCallPolicy.isExpired(100, now: 100))
    XCTAssertFalse(VoipCallPolicy.isExpired(101, now: 100))
  }

}
