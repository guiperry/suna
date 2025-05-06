
-- Query to fix content and metadata fields in a single message (for testing)
UPDATE messages
SET 
    content = 
        CASE 
            -- Handle case where content is improperly JSON-stringified
            WHEN jsonb_typeof(content) = 'string' AND content::text LIKE '{%}' THEN
                content::text::jsonb
            -- Handle case where 'content' field inside the JSON is improperly escaped
            WHEN content ? 'content' AND jsonb_typeof(content->'content') = 'string' AND 
                 (content->'content')::text LIKE '{%}' THEN
                jsonb_set(content, '{content}', (content->'content')::text::jsonb)
            ELSE content
        END,
    metadata = 
        CASE 
            -- Handle case where metadata is improperly JSON-stringified
            WHEN jsonb_typeof(metadata) = 'string' AND metadata::text LIKE '{%}' THEN
                metadata::text::jsonb
            -- Handle case where nested values in metadata need fixing
            WHEN metadata ? 'metadata' AND jsonb_typeof(metadata->'metadata') = 'string' AND 
                 (metadata->'metadata')::text LIKE '{%}' THEN
                jsonb_set(metadata, '{metadata}', (metadata->'metadata')::text::jsonb)
            ELSE metadata
        END
WHERE message_id = '8f6d3f6e-dd1d-4c5f-9170-8265c71637c9'
RETURNING message_id, type, content, metadata;


