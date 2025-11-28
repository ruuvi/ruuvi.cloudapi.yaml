#!/usr/bin/env node
/**
 * Downgrades an OAS 3.1 spec to OAS 3.0 for GitBook compatibility.
 * 
 * Main changes:
 * - Converts openapi: 3.1.0 → 3.0.3
 * - Converts patternProperties → additionalProperties (with documentation)
 * 
 * Usage: node downgrade-to-oas30.js <input.yaml> <output.yaml>
 */

const fs = require('node:fs');
const yaml = require('js-yaml');

const inputPath = process.argv[2];
const outputPath = process.argv[3];

if (!inputPath || !outputPath) {
  console.error('Usage: node downgrade-to-oas30.js <input.yaml> <output.yaml>');
  process.exit(1);
}

const spec = yaml.load(fs.readFileSync(inputPath, 'utf8'));

/**
 * Recursively process the spec to downgrade OAS 3.1 features
 */
function downgrade(obj) {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(downgrade);
  }

  const result = {};

  for (const [key, value] of Object.entries(obj)) {
    // Convert openapi version
    if (key === 'openapi' && value === '3.1.0') {
      result[key] = '3.0.3';
      continue;
    }

    // Convert OAS 3.1 type arrays with null to OAS 3.0 nullable
    // e.g., type: [string, null] → type: string, nullable: true
    if (key === 'type' && Array.isArray(value)) {
      const types = value.filter(t => t !== 'null');
      if (value.includes('null')) {
        result['nullable'] = true;
      }
      if (types.length === 0) {
        // Skip type field if only null was present
        continue;
      }
      result['type'] = types.length === 1 ? types[0] : types;
      continue;
    }

    // Convert patternProperties to additionalProperties with enhanced description
    if (key === 'patternProperties') {
      // Build a description of the pattern constraints
      const patterns = Object.entries(value)
        .map(([pattern, schema]) => `- Pattern \`${pattern}\`: ${schema.description || schema.type}`)
        .join('\n');
      
      const valueSchemas = Object.entries(value);
      
      // Add additionalProperties that accepts any value (since we can't express patterns in 3.0)
      // Use oneOf to allow multiple types based on the patterns
      result['additionalProperties'] = {
        oneOf: valueSchemas.map(([pattern, schema]) => {
          const downgraded = downgrade(schema);
          // Add pattern info to description
          downgraded.description = `${schema.description || ''} (matches pattern: ${pattern})`.trim();
          return downgraded;
        })
      };

      // Append pattern info to parent description if exists
      if (result.description) {
        result.description += `\n\n**Property patterns:**\n${patterns}`;
      }
      
      // Mark that we've handled patternProperties - skip additionalProperties: false if present
      result['_hasPatternProperties'] = true;
      continue;
    }

    // Skip additionalProperties: false if we converted patternProperties
    if (key === 'additionalProperties' && value === false && obj.patternProperties) {
      continue;
    }

    result[key] = downgrade(value);
  }

  // Clean up internal markers
  delete result['_hasPatternProperties'];

  return result;
}

const downgraded = downgrade(spec);

fs.writeFileSync(outputPath, yaml.dump(downgraded, { 
  lineWidth: 120,
  noRefs: true 
}));

console.log(`Downgraded ${inputPath} → ${outputPath} (OAS 3.1 → 3.0.3)`);
