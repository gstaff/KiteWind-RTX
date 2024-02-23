from enum import Enum
from pathlib import Path


class DemoType(Enum):
    GRADIO = 1
    STREAMLIT = 2


gradio_lite_html_template = Path('templates/gradio-lite/gradio-lite-template.html').read_text()
stlite_html_template = Path('templates/stlite/stlite-template.html').read_text()
gradio_lite_snippet_template = Path('templates/gradio-lite/gradio-lite-snippet-template.html').read_text()
stlite_snippet_template = Path('templates/stlite/stlite-snippet-template.html').read_text()


def starting_app_code(demo_type: DemoType) -> str:
    if demo_type == DemoType.GRADIO:
        return Path('templates/gradio-lite/gradio_lite_starting_code.py').read_text().replace('`', r'\`')
    elif demo_type == DemoType.STREAMLIT:
        return Path('templates/stlite/stlite_starting_code.py').read_text().replace('`', r'\`')
    raise NotImplementedError(f'{demo_type} is not a supported demo type')


def load_js(demo_type: DemoType) -> str:
    if demo_type == DemoType.GRADIO:
        return f"""() => {{
            if (window.gradioLiteLoaded) {{
                return
            }}
            
            // Get the query string from the URL
            const queryString = window.location.search;
            // Use a function to parse the query string into an object
            function parseQueryString(queryString) {{
                const params = {{}};
                const queryStringWithoutQuestionMark = queryString.substring(1); // Remove the leading question mark
                const keyValuePairs = queryStringWithoutQuestionMark.split('&');
            
                keyValuePairs.forEach(keyValue => {{
                    const [key, value] = keyValue.split('=');
                    if (value) {{
                        params[key] = decodeURIComponent(value.replace(/\+/g, ' '));
                    }}
                }});
            
                return params;
            }}
            // Parse the query string into an object
            const queryParams = parseQueryString(queryString);
            // Access individual parameters
            const typeValue = queryParams.type;
            let codeValue = null;
            let requirementsValue = null;
            if (typeValue === 'gradio') {{
                codeValue = queryParams.code;
                requirementsValue = queryParams.requirements;
            }}
                        
            const htmlString = '<iframe id="gradio-iframe" width="100%" height="512px" src="about:blank"></iframe>';
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlString, 'text/html');
            const iframe = doc.getElementById('gradio-iframe'); 
            const div = document.getElementById('gradioDemoDiv');
            div.appendChild(iframe);

            let template = `{gradio_lite_html_template.replace('STARTING_CODE', starting_app_code(demo_type))}`;    
            if (codeValue) {{
                template = `{gradio_lite_html_template}`.replace('STARTING_CODE', codeValue.replaceAll(String.fromCharCode(92), String.fromCharCode(92) + String.fromCharCode(92)).replaceAll('`', String.fromCharCode(92) + '`'));
            }}
            template = template.replace('STARTING_REQUIREMENTS', requirementsValue || '');
            const frame = document.getElementById('gradio-iframe');
            frame.contentWindow.document.open('text/html', 'replace');
            frame.contentWindow.document.write(template);
            frame.contentWindow.document.close();
            window.gradioLiteLoaded = true;
        }}"""
    elif demo_type == DemoType.STREAMLIT:
        return f"""() => {{
            if (window.stliteLoaded) {{
                return
            }}
            
            // Get the query string from the URL
            const queryString = window.location.search;
            // Use a function to parse the query string into an object
            function parseQueryString(queryString) {{
                const params = {{}};
                const queryStringWithoutQuestionMark = queryString.substring(1); // Remove the leading question mark
                const keyValuePairs = queryStringWithoutQuestionMark.split('&');
            
                keyValuePairs.forEach(keyValue => {{
                    const [key, value] = keyValue.split('=');
                    if (value) {{
                        params[key] = decodeURIComponent(value.replace(/\+/g, ' '));
                    }}
                }});
            
                return params;
            }}
            // Parse the query string into an object
            const queryParams = parseQueryString(queryString);
            // Access individual parameters
            const typeValue = queryParams.type;
            let codeValue = null;
            let requirementsValue = null;
            if (typeValue === 'streamlit') {{
                codeValue = queryParams.code;
                requirementsValue = queryParams.requirements;
            }}
            
            const htmlString = '<iframe id="stlite-iframe" width="100%" height="512px" src="about:blank"></iframe>';
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlString, 'text/html');
            const iframe = doc.getElementById('stlite-iframe'); 
            const div = document.getElementById('stliteDemoDiv');
            div.appendChild(iframe);
            
            let template = `{stlite_html_template.replace('STARTING_CODE', starting_app_code(demo_type))}`;
            if (codeValue) {{
                template = `{stlite_html_template}`.replace('STARTING_CODE', codeValue.replaceAll(String.fromCharCode(92), String.fromCharCode(92) + String.fromCharCode(92)).replaceAll('`', String.fromCharCode(92) + '`'));
            }}
            const formattedRequirements = (requirementsValue || '').split('\\n').filter(x => x && !x.startsWith('#')).map(x => x.trim());
            template = template.replace('STARTING_REQUIREMENTS', formattedRequirements.map(x => `"${{x}}"`).join(', ') || '');
            const frame = document.getElementById('stlite-iframe');
            frame.contentWindow.document.open();
            frame.contentWindow.document.write(template);
            frame.contentWindow.document.close();
            window.stliteLoaded = true;
        }}"""
    raise NotImplementedError(f'{demo_type} is not a supported demo type')


def update_iframe_js(demo_type: DemoType) -> str:
    if demo_type == DemoType.GRADIO:
        return f"""async (code, requirements, lastError, codeHistory, codeHistoryIndex) => {{
                const formattedRequirements = requirements.split('\\n').filter(x => x && !x.startsWith('#')).map(x => x.trim());
                let errorResult = null;
                const attemptedRequirements = new Set();
                const installedRequirements = [];
                async function update() {{
                    // Remove existing stylesheet so it will be reloaded;
                    // see https://github.com/gradio-app/gradio/blob/200237d73c169f39514465efc163db756969d3ac/js/app/src/lite/css.ts#L41
                    const demoFrameWindow = document.getElementById('gradio-iframe').contentWindow;
                    const oldStyle = demoFrameWindow.document.querySelector("head style");
                    oldStyle.remove();
                    const appController = demoFrameWindow.window.appController;
                    const newCode = code + ` # Update tag ${{Math.random()}}`;
                    try {{
                        await appController.install(formattedRequirements);
                        await appController.run_code(newCode);
                    }}
                    catch (e) {{                    
                        // Replace old style if code error prevented new style from loading.
                        const newStyle = demoFrameWindow.document.querySelector("head style");
                        if (!newStyle) {{
                            demoFrameWindow.document.head.appendChild(oldStyle);
                        }}
                        
                        // If the error is caused by a missing module try once to install it and update again.
                        if (e.toString().includes('ModuleNotFoundError')) {{
                            try {{
                                const guessedModuleName = e.toString().split("'")[1].replaceAll('_', '-');
                                if (attemptedRequirements.has(guessedModuleName)) {{
                                    throw Error(`Could not install pyodide module ${{guessedModuleName}}`);
                                }}
                                console.log(`Attempting to install missing pyodide module "${{guessedModuleName}}"`);
                                attemptedRequirements.add(guessedModuleName);
                                await appController.install([guessedModuleName]);
                                installedRequirements.push(guessedModuleName);
                                return await update();
                            }}
                            catch (err) {{
                                console.log(err);
                            }}
                        }}
                        
                        // Hide app so the error traceback is visible.
                        // First div in main is the error traceback, second is the app.
                        const appBody = demoFrameWindow.document.querySelectorAll("div.main > div")[1];
                        appBody.style.visibility = "hidden";
                        errorResult = e.toString();
                        const allRequirements = formattedRequirements.concat(installedRequirements);
                        return [code, allRequirements, errorResult, codeHistory, codeHistoryIndex];
                    }}
                }};
                await update();
                
                const allRequirements = formattedRequirements.concat(installedRequirements);
                // Update URL query params to include the current demo code state
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.set('type', 'gradio');
                if (requirements) {{
                    currentUrl.searchParams.set('requirements', allRequirements.join('\\n'));
                }}
                if (code) {{
                    currentUrl.searchParams.set('code', code);
                }}
                // Replace the current URL with the updated one
                history.replaceState({{}}, '', currentUrl.href);
                
                return [code, allRequirements, errorResult, codeHistory, codeHistoryIndex];
            }}"""
    elif demo_type == DemoType.STREAMLIT:
        return f"""async (code, requirements, lastError, codeHistory, codeHistoryIndex) => {{
            const formattedRequirements = (requirements || '').split('\\n').filter(x => x && !x.startsWith('#')).map(x => x.trim());
            let errorResult = null;
            const attemptedRequirements = new Set();
            const installedRequirements = [];
            async function update() {{
                const appController = document.getElementById('stlite-iframe').contentWindow.window.appController;
                try {{
                    if (formattedRequirements) {{
                        await appController.install(formattedRequirements);
                    }}
                    const newCode = code + ` # Update tag ${{Math.random()}}`;
                    const entrypointFile = "streamlit_app.py";
                    // As code rerun happens inside streamlit this won't throw an error for self-healing imports.
                    await appController.writeFile(entrypointFile, newCode);
                    // So instead wait 500 milliseconds to see if the streamlit error banner appeared with an error.
                    // TODO: Consider a way to make this not rely on streamlit refresh timing; otherwise user can just re-update and this will trigger.
                    await new Promise(r => setTimeout(r, 500));
                    const messageDiv = document.getElementById('stlite-iframe').contentWindow.document.querySelector('.message');
                    if (messageDiv) {{
                        throw Error(messageDiv.innerHTML);
                    }}
                }}
                catch (e) {{                    
                    // If the error is caused by a missing module try once to install it and update again.
                    if (e.toString().includes('ModuleNotFoundError')) {{
                        try {{
                            const guessedModuleName = e.toString().split("'")[1].replaceAll('_', '-');
                            if (attemptedRequirements.has(guessedModuleName)) {{
                                throw Error(`Could not install pyodide module ${{guessedModuleName}}`);
                            }}
                            console.log(`Attempting to install missing pyodide module "${{guessedModuleName}}"`);
                            attemptedRequirements.add(guessedModuleName);
                            await appController.install([guessedModuleName]);
                            installedRequirements.push(guessedModuleName);
                            return await update();
                        }}
                        catch (err) {{
                            console.log(err);
                        }}
                    }}
                    
                    errorResult = e.toString();
                    const allRequirements = formattedRequirements.concat(installedRequirements);
                    return [code, allRequirements, errorResult, codeHistory, codeHistoryIndex];
                }}
            }};
            await update();
            
            const allRequirements = formattedRequirements.concat(installedRequirements);
            // Update URL query params to include the current demo code state
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('type', 'streamlit');
            if (requirements) {{
                currentUrl.searchParams.set('requirements', allRequirements.join('\\n'));
            }}
            if (code) {{
                currentUrl.searchParams.set('code', code);
            }}
            // Replace the current URL with the updated one
            history.replaceState({{}}, '', currentUrl.href);
            
            return [code, allRequirements, errorResult, codeHistory, codeHistoryIndex];
        }}"""
    raise NotImplementedError(f'{demo_type} is not a supported demo type')


def copy_share_link_js(demo_type: DemoType) -> str:
    if demo_type == DemoType.GRADIO:
        return f"""async (code, requirements) => {{
            const url = new URL(window.location.href);
            url.searchParams.set('type', 'gradio');
            url.searchParams.set('requirements', requirements);
            url.searchParams.set('code', code);
            // TODO: Figure out why link doesn't load as expected in Spaces.
            const shareLink = url.toString().replace('gstaff-kitewind.hf.space', 'huggingface.co/spaces/gstaff/KiteWind');
            await navigator.clipboard.writeText(shareLink);
            return [code, requirements];
        }}"""
    if demo_type == DemoType.STREAMLIT:
        return f"""async (code, requirements) => {{
            const url = new URL(window.location.href);
            url.searchParams.set('type', 'streamlit');
            url.searchParams.set('requirements', requirements);
            url.searchParams.set('code', code);
            // TODO: Figure out why link doesn't load as expected in Spaces.
            const shareLink = url.toString().replace('gstaff-kitewind.hf.space', 'huggingface.co/spaces/gstaff/KiteWind');
            await navigator.clipboard.writeText(shareLink);
            return [code, requirements];
        }}"""
    raise NotImplementedError(f'{demo_type} is not a supported demo type')


def copy_snippet_js(demo_type: DemoType) -> str:
    if demo_type == DemoType.GRADIO:
        return f"""async (code, requirements) => {{
            const escapedCode = code.replaceAll(String.fromCharCode(92), String.fromCharCode(92) + String.fromCharCode(92) + String.fromCharCode(92) + String.fromCharCode(92)).replaceAll('`', String.fromCharCode(92) + '`');
            const template = `{gradio_lite_snippet_template}`;
            // Step 1: Generate the HTML content
            const completedTemplate = template.replace('STARTING_CODE', escapedCode).replace('STARTING_REQUIREMENTS', requirements);
            const snippet = completedTemplate;
            await navigator.clipboard.writeText(snippet);
            return [code, requirements];
        }}"""
    elif demo_type == DemoType.STREAMLIT:
        return f"""async (code, requirements) => {{
            const escapedCode = code.replaceAll(String.fromCharCode(92), String.fromCharCode(92) + String.fromCharCode(92) + String.fromCharCode(92)).replaceAll('`', String.fromCharCode(92) + '`');
            const template = `{stlite_snippet_template}`;
            // Step 1: Generate the HTML content
            const formattedRequirements = (requirements || '').split('\\n').filter(x => x && !x.startsWith('#')).map(x => x.trim());
            const completedTemplate = template.replace('STARTING_CODE', code).replace('STARTING_REQUIREMENTS', formattedRequirements.map(x => `"${{x}}"`).join(', ') || '');
            
            const snippet = completedTemplate;            
            await navigator.clipboard.writeText(snippet);
            return [code, requirements];
        }}"""
    raise NotImplementedError(f'{demo_type} is not a supported demo type')


def download_code_js(demo_type: DemoType) -> str:
    if demo_type == demo_type.GRADIO:
        return f"""(code, requirements) => {{
            const escapedCode = code.replaceAll(String.fromCharCode(92), String.fromCharCode(92) + String.fromCharCode(92)).replaceAll('`', String.fromCharCode(92) + '`');
            // Step 1: Generate the HTML content
            const completedTemplate = `{gradio_lite_html_template}`.replace('STARTING_CODE', escapedCode).replace('STARTING_REQUIREMENTS', requirements);

            // Step 2: Create a Blob from the HTML content
            const blob = new Blob([completedTemplate], {{ type: "text/html" }});

            // Step 3: Create a URL for the Blob
            const url = URL.createObjectURL(blob);

            // Step 4: Create a download link
            const downloadLink = document.createElement("a");
            downloadLink.href = url;
            downloadLink.download = "gradio-lite-app.html"; // Specify the filename for the download

            // Step 5: Trigger a click event on the download link
            downloadLink.click();

            // Clean up by revoking the URL
            URL.revokeObjectURL(url);
        }}"""
    elif demo_type == demo_type.STREAMLIT:
        return f"""(code, requirements) => {{
            const escapedCode = code.replaceAll(String.fromCharCode(92), String.fromCharCode(92) + String.fromCharCode(92)).replaceAll('`', String.fromCharCode(92) + '`');
            // Step 1: Generate the HTML content
            const formattedRequirements = (requirements || '').split('\\n').filter(x => x && !x.startsWith('#')).map(x => x.trim());
            const completedTemplate = `{stlite_html_template}`.replace('STARTING_CODE', escapedCode).replace('STARTING_REQUIREMENTS', formattedRequirements.map(x => `"${{x}}"`).join(', ') || '');
            
            // Step 2: Create a Blob from the HTML content
            const blob = new Blob([completedTemplate], {{ type: "text/html" }});
            
            // Step 3: Create a URL for the Blob
            const url = URL.createObjectURL(blob);
            
            // Step 4: Create a download link
            const downloadLink = document.createElement("a");
            downloadLink.href = url;
            downloadLink.download = "stlite-app.html"; // Specify the filename for the download
            
            // Step 5: Trigger a click event on the download link
            downloadLink.click();
            
            // Clean up by revoking the URL
            URL.revokeObjectURL(url);
        }}"""
    raise NotImplementedError(f'{demo_type} is not a supported demo type')
