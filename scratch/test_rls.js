import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://miezybwngeqdyqvvqcrl.supabase.co';
const SUPABASE_KEY = 'sb_publishable_9rv6kPFg1nCNl0tYSZBiTA_31vInJ6M'; 

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

async function testRls() {
    console.log("Testing RLS on 'units' table with anonymous access...");
    const { data: anonData, error: anonError } = await supabase.from('units').select('*');
    
    if (anonError) {
        console.error("Anon access error:", anonError);
    } else {
        console.log(`Anon access returned ${anonData.length} records.`);
        if (anonData.length === 0) {
            console.log("SUCCESS: RLS is active and blocked reading for anonymous user.");
        } else {
            console.log("FAILURE: RLS allowed reading rows!");
        }
    }
}

testRls();

