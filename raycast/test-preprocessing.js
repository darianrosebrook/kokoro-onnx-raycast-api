// Simple test to verify text preprocessing fixes
const testCases = [
  {
    name: "SSML with breaks",
    input: '<speak>Hello world<break time="35ms"/>How are you?</speak>',
    expected: "Hello world How are you?",
  },
  {
    name: "Text with emojis and bullets",
    input: "✅ Yes • Item 1 • Item 2\nNew line with emoji 🚀",
    expected: "Yes Item 1 Item 2 New line with emoji",
  },
  {
    name: "Complex formatting",
    input: '<speak>1. First item<break time="35ms"/>2. Second item\n• Bullet point</speak>',
    expected: "1. First item 2. Second item Bullet point",
  },
  {
    name: "Empty after preprocessing",
    input: "<speak></speak>",
    expected: "No text to speak",
  },
];

// Simulate the preprocessing function
function preprocessText(text) {
  // 1. Remove all SSML tags entirely (kokoro-onnx doesn't support SSML)
  // Replace SSML tags with spaces to maintain word separation
  let t = text.replace(/<[^>]+>/g, " ");

  // 2. Remove all newlines and normalize whitespace
  t = t
    .replace(/[\r\n]+/g, " ") // Remove line breaks
    .replace(/\s+/g, " ") // Collapse spaces
    .trim();

  // 3. Escape XML entities and remove control characters
  t = t
    .replace(/&/g, "and")
    .replace(/</g, "")
    .replace(/>/g, "")
    .replace(/[\u0000-\u001F\u007F]+/g, ""); // Remove control chars

  // 4. Handle emoji and special characters that might cause issues
  // Remove emojis and bullet points, replace with spaces
  t = t
    .replace(
      /[\u{1F600}-\u{1F64F}]|[\u{1F300}-\u{1F5FF}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu,
      " "
    ) // Remove emojis
    .replace(/[•·]/g, " ") // Replace bullet points with spaces
    .replace(/\s+/g, " ") // Re-collapse spaces after removal
    .trim();

  // 5. Ensure we have valid text
  if (!t || t.length === 0) {
    return "No text to speak";
  }

  return t;
}

// Run tests
console.log("🧪 Testing text preprocessing fixes...\n");

let passed = 0;
let failed = 0;

testCases.forEach((testCase, index) => {
  const result = preprocessText(testCase.input);
  const success = result === testCase.expected;

  console.log(`Test ${index + 1}: ${testCase.name}`);
  console.log(`  Input:    "${testCase.input}"`);
  console.log(`  Expected: "${testCase.expected}"`);
  console.log(`  Result:   "${result}"`);
  console.log(`  Status:   ${success ? "✅ PASS" : "❌ FAIL"}`);
  console.log("");

  if (success) {
    passed++;
  } else {
    failed++;
  }
});

console.log(`📊 Results: ${passed} passed, ${failed} failed`);
console.log(failed === 0 ? "🎉 All tests passed!" : "⚠️ Some tests failed");

// Test segmentation
function segmentTextForPauses(text) {
  if (!text?.trim()) return [];

  // Split on sentence boundaries and major punctuation
  const segments = text
    .split(/([.!?])\s+/) // Split on sentence endings
    .filter((segment) => segment.trim().length > 0)
    .map((segment) => segment.trim());

  // If no sentence boundaries found, split on commas and other punctuation
  if (segments.length <= 1) {
    return text
      .split(/([,;:—–])\s*/)
      .filter((segment) => segment.trim().length > 0)
      .map((segment) => segment.trim());
  }

  // Reconstruct segments properly by combining text with its punctuation
  const reconstructedSegments = [];
  for (let i = 0; i < segments.length; i += 2) {
    if (i + 1 < segments.length) {
      // Combine text with its punctuation
      reconstructedSegments.push(segments[i] + segments[i + 1]);
    } else {
      // Last segment without punctuation
      reconstructedSegments.push(segments[i]);
    }
  }

  return reconstructedSegments;
}

console.log("\n🧪 Testing text segmentation...\n");

const segmentationTests = [
  {
    name: "Simple sentences",
    input: "Hello world. How are you? I am fine.",
    expected: ["Hello world.", "How are you?", "I am fine."],
  },
  {
    name: "Comma separated",
    input: "Hello, world, how are you",
    expected: ["Hello", ",", "world", ",", "how are you"],
  },
];

segmentationTests.forEach((testCase, index) => {
  const result = segmentTextForPauses(testCase.input);
  const success = JSON.stringify(result) === JSON.stringify(testCase.expected);

  console.log(`Segmentation Test ${index + 1}: ${testCase.name}`);
  console.log(`  Input:    "${testCase.input}"`);
  console.log(`  Expected: [${testCase.expected.map((s) => `"${s}"`).join(", ")}]`);
  console.log(`  Result:   [${result.map((s) => `"${s}"`).join(", ")}]`);
  console.log(`  Status:   ${success ? "✅ PASS" : "❌ FAIL"}`);
  console.log("");
});
