# How to Use the License Suggestion Feature

## When does the suggestion form appear?

The license suggestion form automatically appears when:

1. **No main license detected**: The system cannot find a valid `LICENSE` or `COPYING` file in the repository.
2. **Unknown licenses present**: Some files have licenses that cannot be correctly identified by ScanCode.

## How to use the form

### Step 1: Fill in Permissions & Requirements

Select the permissions you desire for your license:

- ☑️ **Commercial use allowed**: The software can be used for commercial purposes.
- ☑️ **Modification allowed**: The code can be modified.
- ☑️ **Distribution allowed**: The software can be distributed.
- ☐ **Patent grant required**: Includes an explicit grant of patent rights.
- ☐ **Trademark use allowed**: Permits the use of the project's trademarks.
- ☐ **Liability protection needed**: Includes disclaimer of liability clauses.

### Step 2: Choose the Copyleft Preference

Select the desired level of copyleft:

- **No Copyleft (Permissive)**: Permissive licenses like MIT, Apache-2.0, BSD
  - Maximum freedom for those who use the code.
  - No obligation to release modifications.
  - Examples: MIT, Apache-2.0, BSD-3-Clause.

- **Weak Copyleft (LGPL-style)**: Weak copyleft
  - Modifications to the library must be shared.
  - Software using it can remain proprietary.
  - Examples: LGPL-3.0, MPL-2.0.

- **Strong Copyleft (GPL-style)**: Strong copyleft
  - All derivative software must be open source.
  - The same license must be applied.
  - Examples: GPL-3.0, AGPL-3.0.

### Step 3: Additional Requirements (Optional)

You can add additional requirements in free text, for example:
- "The project must be compatible with Android projects"
- "I want modifications to always be shared"
- "Need for patent protection"

### Step 4: Get Suggestion

Click on "Get Suggestion" and the AI will analyze your requirements to suggest the most suitable license.

## Interpreting the result

### Recommended License
The main suggested license based on your requirements.

### Explanation
A detailed explanation of why this license is appropriate for your needs.

### Alternative Options
A list of alternative licenses that might still meet your requirements.

## Scenario Examples

### Scenario 1: Corporate Open Source Project
**Requirements:**
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Patent grant
- No Copyleft

**Probable suggestion:** Apache-2.0
- Permissive but with explicit patent protection.

### Scenario 2: Open Source Library for the Community
**Requirements:**
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- Weak Copyleft

**Probable suggestion:** LGPL-3.0
- Modifications to the library are shared, but projects using it can remain proprietary.

### Scenario 3: Completely Free Software
**Requirements:**
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- Strong Copyleft
- Additional: "All derivative code must remain open source"

**Probable suggestion:** GPL-3.0
- Ensures that all derivative software is open source.

### Scenario 4: Simple and Permissive Project
**Requirements:**
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- No Copyleft

**Probable suggestion:** MIT
- The simplest and most permissive license.

## What to do after receiving the suggestion

1. **Carefully read the explanation** to understand the implications of the license.
2. **Consider the alternatives** if the suggested license doesn't completely convince you.
3. **Research further information** on the suggested license (e.g., on choosealicense.com).
4. **Add a LICENSE file** to your repository with the text of the chosen license.
5. **Update the source files** with the appropriate copyright header.

## Important Notes

- ⚠️ This is an AI suggestion, not legal advice.
- ⚠️ Always consult a lawyer for important legal decisions.
- ⚠️ Verify compatibility with dependency licenses.
- ⚠️ Some licenses have specific requirements (e.g., NOTICE files, copyright headers).

## Useful Resources

- [Choose a License](https://choosealicense.com/) - Visual guide to licenses
- [SPDX License List](https://spdx.org/licenses/) - Comprehensive list of standard licenses
- [TLDRLegal](https://tldrlegal.com/) - Simplified explanations of licenses
- [GNU License Recommendations](https://www.gnu.org/licenses/license-recommendations.html)

## Support

If you have questions or issues with the license suggestion, please open an issue in the project repository.
